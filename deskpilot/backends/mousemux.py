"""Optional MouseMux V2 Windows SDK transport for independent hand pointers.

Uses the documented registered-window-message interface. Never falls back to
SendInput: doing so would silently merge the two independent pointers.
"""

import secrets
import sys
from ctypes import wintypes

from .windows import WindowsBackend

SETTER = "mousemux-api-window-setter"
FLAGS = {
    (1, True): 1,
    (1, False): 2,
    (3, True): 4,
    (3, False): 8,
    (2, True): 16,
    (2, False): 32,
}


class MouseMuxBackend(WindowsBackend):
    name = "Windows • MouseMux V2 (dua pointer)"

    def __init__(self, user32=None):
        super().__init__(user32)
        self.messages = {}
        self.users = {}
        self.buttons = {"Right": set(), "Left": set()}
        self.windows = {}
        self.hwnd = None

    def start(self):
        if self.user32 is None and sys.platform != "win32":
            raise RuntimeError("MouseMux hanya tersedia pada Windows")
        # The parent configures Win32 window inspection, but does not send input.
        super().start()
        self.ready = False
        if sys.platform == "win32":
            self.user32.RegisterWindowMessageW.argtypes = (wintypes.LPCWSTR,)
            self.user32.RegisterWindowMessageW.restype = wintypes.UINT
            self.user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
            self.user32.FindWindowW.restype = wintypes.HWND
            self.user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
            self.user32.PostMessageW.restype = wintypes.BOOL
        self.hwnd = self._find()
        if not self.hwnd:
            raise RuntimeError("MouseMux V2 SDK tidak aktif: jalankan MouseMux dan aktifkan SDK")
        keys = ("user.create", "user.dispose", "user.pointer.motion", "user.pointer.button")
        for key in keys:
            mid = self.user32.RegisterWindowMessageW("mousemux.api.set." + key)
            if not mid:
                raise RuntimeError("Gagal mendaftarkan pesan SDK MouseMux")
            self.messages[key] = mid
        # Ephemeral IDs avoid colliding with users created by other SDK clients.
        base = 0x60000000 + 4 * secrets.randbelow(0x03FFFFFE)
        self.users = {"Right": (base, base + 1), "Left": (base + 2, base + 3)}
        try:
            for mouse, keyboard in self.users.values():
                self._post("user.create", mouse, keyboard)
        except Exception:
            self.close()
            raise
        self.ready = True

    def _find(self):
        return self.user32.FindWindowW(SETTER, SETTER)

    def _post(self, key, mouse, data):
        hwnd = self._find()
        if not hwnd or hwnd != self.hwnd:
            raise RuntimeError("Koneksi MouseMux terputus; input dihentikan")
        if not self.user32.PostMessageW(hwnd, self.messages[key], mouse, data):
            raise RuntimeError("MouseMux menolak pesan input")

    def pump(self):
        if self._find() != self.hwnd:
            self.ready = False
            self.error = "Koneksi MouseMux terputus"

    def _move(self, side, x, y):
        self._refresh_geometry()
        px, py = self._pixel_position(x, y)
        if not (-32768 <= px <= 32767 and -32768 <= py <= 32767):
            raise RuntimeError("Koordinat desktop melebihi batas MouseMux V2 SDK")
        self._post("user.pointer.motion", self.users[side][0], (px & 0xFFFF) | ((py & 0xFFFF) << 16))
        if side in self.windows:
            kind, handle, start, rect = self.windows[side]
            dx, dy = (x - start[0]) * self.width, (y - start[1]) * self.height
            left, top, right, bottom = rect
            if kind == "window":
                self._set_window(handle, left + dx, top + dy, right - left, bottom - top)
            else:
                self._set_window(handle, left, top, max(160, right - left + dx), max(100, bottom - top + dy))

    def _button(self, side, button, down):
        self._post("user.pointer.button", self.users[side][0], FLAGS[(button, down)])
        if down:
            self.buttons[side].add(button)
        else:
            self.buttons[side].discard(button)

    def release_side(self, side):
        self.windows.pop(side, None)
        for button in tuple(self.buttons[side]):
            self._button(side, button, False)

    def release(self):
        errors = []
        for side in self.buttons:
            try:
                self.release_side(side)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise RuntimeError(f"Gagal melepas tombol MouseMux: {errors[0]}")

    def execute(self, action):
        if action.kind == "release":
            if action.side is None:
                self.release()
            else:
                self.release_side(action.side)
            return
        if not self.ready:
            raise RuntimeError("MouseMux belum siap")
        if action.side not in self.users:
            raise ValueError("Aksi MouseMux memerlukan label tangan")
        side = action.side
        if action.kind == "pointer_at":
            self._move(side, *action.values)
        elif action.kind == "left_down_at":
            self._move(side, *action.values)
            self._button(side, 1, True)
        elif action.kind == "right_click_at":
            self._move(side, *action.values)
            try:
                self._button(side, 3, True)
            finally:
                self.release_side(side)
        elif action.kind in ("begin_window", "begin_resize"):
            x, y = action.values
            self._refresh_geometry()
            px, py = self._pixel_position(x, y)
            handle = self._window_at(px, py)
            if not handle or self.user32.IsZoomed(handle) or self.user32.IsIconic(handle):
                raise RuntimeError("Pilih jendela normal (tidak maximized/minimized) untuk pindah/resize")
            self._move(side, x, y)
            self.windows[side] = (action.kind.removeprefix("begin_"), handle, (x, y), self._window_rect(handle))
        else:
            raise ValueError(f"Aksi MouseMux tidak tersedia: {action.kind}")

    def close(self):
        try:
            self.release()
        finally:
            for mouse, keyboard in self.users.values():
                try:
                    self._post("user.dispose", mouse, keyboard)
                except Exception:
                    pass
            self.users.clear()
            self.ready = False
