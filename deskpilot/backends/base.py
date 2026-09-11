"""Common input ownership and action execution, extensible to AI / voice later."""


class DesktopBackend:
    name = "Desktop"
    ready = False
    error = ""
    width = 1920
    height = 1080
    modifier = "Super_L"
    resize_button = 3

    def __init__(self):
        self.held_buttons = set()
        self.held_keys = set()

    def start(self):
        self.ready = True

    def absolute(self, x, y):
        raise NotImplementedError

    def relative(self, dx, dy):
        raise NotImplementedError

    def button(self, button, down):
        raise NotImplementedError

    def key(self, key, down):
        raise NotImplementedError

    def hold_button(self, button):
        self.held_buttons.add(button)
        self.button(button, True)

    def hold_key(self, key):
        self.held_keys.add(key)
        self.key(key, True)

    def release(self):
        errors = []
        for button in list(self.held_buttons):
            try:
                self.button(button, False)
                self.held_buttons.discard(button)
            except Exception as exc:
                errors.append(exc)
        for key in list(self.held_keys):
            try:
                self.key(key, False)
                self.held_keys.discard(key)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise RuntimeError(f"Gagal melepas input: {errors[0]}")

    def execute(self, action):
        if action.kind == "release":
            self.release()
            return
        if not self.ready:
            raise RuntimeError(self.error or "Backend belum siap")
        if action.kind == "move":
            self.relative(action.values[0] * self.width, action.values[1] * self.height)
        elif action.kind in ("click_at", "begin_window", "begin_resize"):
            self.absolute(*action.values)
            if action.kind == "click_at":
                try:
                    self.hold_button(1)
                finally:
                    self.release()
            else:
                try:
                    self.hold_key(self.modifier)
                    self.hold_button(1 if action.kind == "begin_window" else self.resize_button)
                except Exception:
                    self.release()
                    raise
        elif action.kind == "zoom":
            try:
                self.hold_key("Control_L")
                for _ in range(abs(action.values[0])):
                    self.hold_button(4 if action.values[0] > 0 else 5)
                    self.release_scroll()
            finally:
                self.release()
        else:
            raise ValueError(f"Tindakan tidak dikenal: {action.kind}")

    def release_scroll(self):
        for button in (4, 5):
            if button in self.held_buttons:
                self.button(button, False)
                self.held_buttons.discard(button)

    def close(self):
        try:
            self.release()
        finally:
            self.ready = False


class PreviewBackend(DesktopBackend):
    name = "Preview • tanpa input desktop"

    def __init__(self):
        super().__init__()
        self.events = []

    def _record(self, *event):
        self.events.append(event)
        self.events = self.events[-100:]

    def absolute(self, x, y):
        self._record("absolute", x, y)

    def relative(self, dx, dy):
        self._record("relative", dx, dy)

    def button(self, button, down):
        self._record("button", button, down)

    def key(self, key, down):
        self._record("key", key, down)
