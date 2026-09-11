import pytest

from deskpilot.backends.base import PreviewBackend
from deskpilot.gestures import Action


def backend():
    b = PreviewBackend()
    b.start()
    return b


def test_direct_click_moves_once_then_clicks_and_releases():
    b = backend()
    b.execute(Action("click_at", (0.2, 0.3)))
    assert b.events == [("absolute", 0.2, 0.3), ("button", 1, True), ("button", 1, False)]
    assert not b.held_buttons


def test_window_move_and_resize_release_modifiers():
    for mode, button in (("window", 1), ("resize", 3)):
        b = backend()
        b.execute(Action("begin_" + mode, (0.4, 0.4)))
        assert b.held_buttons == {button} and b.held_keys == {"Super_L"}
        b.execute(Action("release"))
        assert not b.held_buttons and not b.held_keys


def test_zoom_releases_control_even_on_input_failure():
    class Broken(PreviewBackend):
        def button(self, button, down):
            if down:
                raise RuntimeError("disconnected")
            super().button(button, down)

    b = Broken()
    b.start()
    with pytest.raises(RuntimeError):
        b.execute(Action("zoom", (1,)))
    assert not b.held_keys and not b.held_buttons


def test_release_attempts_other_inputs_after_one_failure():
    class Broken(PreviewBackend):
        def button(self, button, down):
            raise RuntimeError("button failed")

    b = Broken()
    b.held_buttons.add(1)
    b.held_keys.add("Control_L")
    with pytest.raises(RuntimeError):
        b.release()
    assert not b.held_keys
    assert b.held_buttons == {1}  # retained for cleanup retry


def test_zoom_and_unknown_action():
    b = backend()
    b.execute(Action("zoom", (-2,)))
    assert b.events.count(("button", 5, True)) == 2
    assert not b.held_keys
    with pytest.raises(ValueError):
        b.execute(Action("shell", ("anything",)))
