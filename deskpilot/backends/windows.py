"""Native Windows input and window manipulation through the Win32 API."""

import ctypes
import sys
from ctypes import wintypes

from .base import DesktopBackend

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000
WHEEL_DELTA = 120

SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
GA_ROOT = 2
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010


class MOUSEINPUT(ctypes.Structure):
    _fields_ = (
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class KEYBDINPUT(ctypes.Structure):
    _fields_ = (
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    )


class INPUT_UNION(ctypes.Union):
    _fields_ = (("mi", MOUSEINPUT), ("ki", KEYBDINPUT))


class INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = (("type", wintypes.DWORD), ("data", INPUT_UNION))


class WindowsBackend(DesktopBackend):
    """Send pointer/keyboard events and move windows without extra packages."""

    name = "Windows • SendInput"
    key_codes = {"Control_L": 0xA2, "Super_L": 0x5B, "Alt_L": 0xA4}

    def __init__(self, user32=None):
        super().__init__()
        self.user32 = user32
        self.left = self.top = 0
        self.window_action = None

    def start(self):
        if self.user32 is None:
            if sys.platform != "win32":
                raise RuntimeError("Backend Windows hanya dapat dijalankan pada Windows")
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            self._configure_api()
        self._refresh_geometry()
        self.ready = True

    def _configure_api(self):
        self.user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self.user32.SendInput.restype = wintypes.UINT
        self.user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
        self.user32.GetSystemMetrics.restype = ctypes.c_int
        self.user32.WindowFromPoint.argtypes = (wintypes.POINT,)
        self.user32.WindowFromPoint.restype = wintypes.HWND
        self.user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        self.user32.GetAncestor.restype = wintypes.HWND
        self.user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
        self.user32.GetWindowRect.restype = wintypes.BOOL
        self.user32.IsZoomed.argtypes = (wintypes.HWND,)
        self.user32.IsZoomed.restype = wintypes.BOOL
        self.user32.IsIconic.argtypes = (wintypes.HWND,)
        self.user32.IsIconic.restype = wintypes.BOOL
        self.user32.SetWindowPos.argtypes = (
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        )
        self.user32.SetWindowPos.restype = wintypes.BOOL

    def _refresh_geometry(self):
        self.left = self.user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self.top = self.user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        self.width = self.user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        self.height = self.user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        if self.width <= 0 or self.height <= 0:
            raise RuntimeError("Ukuran desktop virtual Windows tidak valid")

    def _send(self, event):
        if self.user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
            code = getattr(ctypes, "get_last_error", lambda: 0)()
            raise RuntimeError(f"Windows SendInput gagal (kode {code})")

    def _send_mouse(self, flags, data=0, dx=0, dy=0):
        self._send(INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dx, dy, data, flags, 0, 0)))

    def _pixel_position(self, x, y):
        return (
            self.left + round(max(0, min(1, x)) * max(0, self.width - 1)),
            self.top + round(max(0, min(1, y)) * max(0, self.height - 1)),
        )

    def absolute(self, x, y):
        x, y = max(0, min(1, x)), max(0, min(1, y))
        self._send_mouse(
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
            dx=round(x * 65535),
            dy=round(y * 65535),
        )
        self._update_window_action(x, y)

    def relative(self, dx, dy):
        self._send_mouse(MOUSEEVENTF_MOVE, dx=round(dx), dy=round(dy))

    def button(self, button, down):
        flags = {
            (1, True): MOUSEEVENTF_LEFTDOWN,
            (1, False): MOUSEEVENTF_LEFTUP,
            (2, True): MOUSEEVENTF_MIDDLEDOWN,
            (2, False): MOUSEEVENTF_MIDDLEUP,
            (3, True): MOUSEEVENTF_RIGHTDOWN,
            (3, False): MOUSEEVENTF_RIGHTUP,
        }
        if button in (4, 5):
            if down:
                self._send_mouse(MOUSEEVENTF_WHEEL, WHEEL_DELTA if button == 4 else -WHEEL_DELTA)
            return
        try:
            flag = flags[(button, down)]
        except KeyError as exc:
            raise ValueError(f"Tombol mouse Windows tidak dikenal: {button}") from exc
        self._send_mouse(flag)

    def key(self, key, down):
        try:
            code = self.key_codes[key]
        except KeyError as exc:
            raise ValueError(f"Tombol keyboard Windows tidak dikenal: {key}") from exc
        flags = KEYEVENTF_KEYUP if not down else 0
        self._send(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(code, 0, flags, 0, 0)))

    def _window_at(self, px, py):
        handle = self.user32.WindowFromPoint(wintypes.POINT(px, py))
        return self.user32.GetAncestor(handle, GA_ROOT) if handle else None

    def _window_rect(self, handle):
        rect = wintypes.RECT()
        if not self.user32.GetWindowRect(handle, ctypes.byref(rect)):
            raise RuntimeError("Windows tidak dapat membaca ukuran jendela target")
        return rect.left, rect.top, rect.right, rect.bottom

    def _set_window(self, handle, x, y, width, height):
        if not self.user32.SetWindowPos(
            handle,
            None,
            round(x),
            round(y),
            round(width),
            round(height),
            SWP_NOZORDER | SWP_NOACTIVATE,
        ):
            code = getattr(ctypes, "get_last_error", lambda: 0)()
            raise RuntimeError(f"Windows menolak perubahan jendela (kode {code})")

    def _begin_window_action(self, kind, x, y):
        px, py = self._pixel_position(x, y)
        handle = self._window_at(px, py)
        if not handle:
            raise RuntimeError("Tidak ada jendela di bawah kursor")
        if self.user32.IsZoomed(handle) or self.user32.IsIconic(handle):
            raise RuntimeError("Pulihkan jendela dari maximized/minimized sebelum dipindah atau di-resize")
        self.window_action = (kind, handle, (x, y), self._window_rect(handle))

    def _update_window_action(self, x, y):
        if not self.window_action:
            return
        kind, handle, start, rect = self.window_action
        dx = (x - start[0]) * self.width
        dy = (y - start[1]) * self.height
        left, top, right, bottom = rect
        width, height = right - left, bottom - top
        if kind == "window":
            self._set_window(handle, left + dx, top + dy, width, height)
        else:
            self._set_window(handle, left, top, max(160, width + dx), max(100, height + dy))

    def execute(self, action):
        if action.kind in ("begin_window", "begin_resize"):
            if not self.ready:
                raise RuntimeError(self.error or "Backend belum siap")
            self.absolute(*action.values)
            self._begin_window_action(action.kind.removeprefix("begin_"), *action.values)
            return
        super().execute(action)

    def release(self):
        self.window_action = None
        super().release()
