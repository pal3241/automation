"""Windows backend tests run with a fake user32 library on every CI platform."""

import ctypes

import pytest

from deskpilot.backends.windows import (
    INPUT,
    INPUT_KEYBOARD,
    INPUT_MOUSE,
    KEYEVENTF_KEYUP,
    MOUSEEVENTF_ABSOLUTE,
    MOUSEEVENTF_LEFTDOWN,
    MOUSEEVENTF_LEFTUP,
    MOUSEEVENTF_MOVE,
    MOUSEEVENTF_RIGHTDOWN,
    MOUSEEVENTF_RIGHTUP,
    MOUSEEVENTF_VIRTUALDESK,
    MOUSEEVENTF_WHEEL,
    SM_CXVIRTUALSCREEN,
    SM_CYVIRTUALSCREEN,
    SM_XVIRTUALSCREEN,
    SM_YVIRTUALSCREEN,
    WHEEL_DELTA,
    WindowsBackend,
)
from deskpilot.gestures import Action


class FakeUser32:
    def __init__(self):
        self.events = []
        self.metrics = {
            SM_XVIRTUALSCREEN: -1920,
            SM_YVIRTUALSCREEN: 0,
            SM_CXVIRTUALSCREEN: 3840,
            SM_CYVIRTUALSCREEN: 1080,
        }

    def GetSystemMetrics(self, metric):
        return self.metrics[metric]

    def SendInput(self, count, pointer, size):
        assert count == 1 and size == ctypes.sizeof(INPUT)
        event = ctypes.cast(pointer, ctypes.POINTER(INPUT)).contents
        if event.type == INPUT_MOUSE:
            self.events.append(("mouse", event.mi.dx, event.mi.dy, event.mi.mouseData, event.mi.dwFlags))
        elif event.type == INPUT_KEYBOARD:
            self.events.append(("key", event.ki.wVk, event.ki.dwFlags))
        return 1

    def IsZoomed(self, handle):
        return False

    def IsIconic(self, handle):
        return False


def backend(cls=WindowsBackend):
    result = cls(FakeUser32())
    result.start()
    return result


def test_absolute_pointer_uses_whole_virtual_desktop():
    result = backend()
    assert (result.left, result.top, result.width, result.height) == (-1920, 0, 3840, 1080)
    result.absolute(0.25, 0.75)
    assert result.user32.events[-1] == (
        "mouse",
        round(0.25 * 65535),
        round(0.75 * 65535),
        0,
        MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK,
    )
    assert result._pixel_position(0.25, 0.75) == (-960, 809)


def test_click_scroll_and_keyboard_events_release_cleanly():
    result = backend()
    result.execute(Action("left_down_at", (0.5, 0.5)))
    result.execute(Action("release"))
    result.execute(Action("right_click_at", (0.4, 0.4)))
    result.execute(Action("zoom", (1,)))
    flags = [event[-1] for event in result.user32.events if event[0] == "mouse"]
    assert MOUSEEVENTF_LEFTDOWN in flags and MOUSEEVENTF_LEFTUP in flags
    assert MOUSEEVENTF_RIGHTDOWN in flags and MOUSEEVENTF_RIGHTUP in flags
    wheel = [event for event in result.user32.events if event[0] == "mouse" and event[-1] == MOUSEEVENTF_WHEEL]
    assert wheel == [("mouse", 0, 0, WHEEL_DELTA, MOUSEEVENTF_WHEEL)]
    keys = [event for event in result.user32.events if event[0] == "key"]
    assert keys[-2:] == [("key", 0xA2, 0), ("key", 0xA2, KEYEVENTF_KEYUP)]
    assert not result.held_buttons and not result.held_keys


class WindowBackend(WindowsBackend):
    def __init__(self, user32):
        super().__init__(user32)
        self.changes = []

    def _window_at(self, px, py):
        assert (px, py) == (0, 540)
        return 42

    def _window_rect(self, handle):
        assert handle == 42
        return 100, 200, 900, 800

    def _set_window(self, handle, x, y, width, height):
        self.changes.append((handle, round(x), round(y), round(width), round(height)))


@pytest.mark.parametrize(
    ("kind", "expected"),
    (("window", (42, 484, 308, 800, 600)), ("resize", (42, 100, 200, 1184, 708))),
)
def test_native_window_move_and_resize(kind, expected):
    result = backend(WindowBackend)
    result.execute(Action("begin_" + kind, (0.5, 0.5)))
    result.execute(Action("pointer_at", (0.6, 0.6)))
    assert result.changes[-1] == expected
    result.execute(Action("release"))
    assert result.window_action is None


def test_windows_backend_rejects_invalid_mouse_and_key():
    result = backend()
    with pytest.raises(ValueError):
        result.button(99, True)
    with pytest.raises(ValueError):
        result.key("DeleteEverything", True)
