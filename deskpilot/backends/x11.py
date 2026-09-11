from .base import DesktopBackend


class X11Backend(DesktopBackend):
    name = "X11 • XTest"

    def start(self):
        from Xlib import X, display
        from Xlib.ext import xtest

        self.X, self.xtest = X, xtest
        self.display = display.Display()
        if not self.display.has_extension("XTEST"):
            self.display.close()
            raise RuntimeError("X server tidak menyediakan XTEST")
        self.root = self.display.screen().root
        geometry = self.root.get_geometry()
        self.width, self.height = geometry.width, geometry.height
        self.ready = True

    def absolute(self, x, y):
        self.xtest.fake_input(
            self.display,
            self.X.MotionNotify,
            x=int(max(0, min(1, x)) * (self.width - 1)),
            y=int(max(0, min(1, y)) * (self.height - 1)),
        )
        self.display.sync()

    def relative(self, dx, dy):
        pointer = self.root.query_pointer()
        self.absolute(
            (pointer.root_x + dx) / max(1, self.width - 1), (pointer.root_y + dy) / max(1, self.height - 1)
        )

    def button(self, button, down):
        self.xtest.fake_input(self.display, self.X.ButtonPress if down else self.X.ButtonRelease, button)
        self.display.sync()

    def key(self, key, down):
        from Xlib import XK

        code = self.display.keysym_to_keycode(XK.string_to_keysym(key))
        if not code:
            raise RuntimeError(f"Key tidak tersedia: {key}")
        self.xtest.fake_input(self.display, self.X.KeyPress if down else self.X.KeyRelease, code)
        self.display.sync()

    def close(self):
        try:
            super().close()
        finally:
            if hasattr(self, "display"):
                self.display.close()
