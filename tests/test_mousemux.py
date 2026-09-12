"""The MouseMux transport is mockable without a Windows computer or MouseMux install."""

import pytest
from test_gestures import hand

from deskpilot.backends.mousemux import FLAGS, MouseMuxBackend
from deskpilot.gestures import Action, GestureEngine, Settings


class FakeUser32:
    def __init__(self):
        self.events = []
        self.running = True

    def GetSystemMetrics(self, key):
        return {76: -1920, 77: 0, 78: 3840, 79: 1080}[key]

    def FindWindowW(self, cls, title):
        return 10 if self.running and cls == title == "mousemux-api-window-setter" else 0

    def RegisterWindowMessageW(self, name):
        return {"mousemux.api.set." + key: i for i, key in enumerate(
            ("user.create", "user.dispose", "user.pointer.motion", "user.pointer.button"), 100
        )}[name]

    def PostMessageW(self, handle, code, user, data):
        self.events.append((code, user, data))
        return 1


def test_two_hands_move_and_click_independently():
    fake = FakeUser32()
    backend = MouseMuxBackend(fake)
    backend.start()
    right, left = (backend.users[s][0] for s in ("Right", "Left"))
    assert right != left
    backend.execute(Action("left_down_at", (0.4, 0.5), "Right"))
    backend.execute(Action("left_down_at", (0.6, 0.5), "Left"))
    backend.execute(Action("pointer_at", (0.2, 0.5), "Left"))
    backend.execute(Action("release", side="Right"))
    assert backend.buttons["Left"] == {1}
    assert backend.buttons["Right"] == set()
    motions = [(who, data) for code, who, data in fake.events if code == 102]
    assert motions[0][0] == right and motions[1][0] == left and motions[2][0] == left
    buttons = [(who, flag) for code, who, flag in fake.events if code == 103]
    assert buttons == [(right, FLAGS[1, True]), (left, FLAGS[1, True]), (right, FLAGS[1, False])]
    backend.close()
    assert backend.buttons["Left"] == set()
    assert sum(event[0] == 101 for event in fake.events) == 2


def test_missing_sdk_fails_without_sendinput_fallback():
    fake = FakeUser32()
    fake.running = False
    with pytest.raises(RuntimeError, match="MouseMux V2 SDK tidak aktif"):
        MouseMuxBackend(fake).start()


def test_sdk_disconnect_preserves_release_for_retry():
    fake = FakeUser32()
    backend = MouseMuxBackend(fake)
    backend.start()
    backend.execute(Action("left_down_at", (0.4, 0.4), "Left"))
    fake.running = False
    with pytest.raises(RuntimeError, match="terputus"):
        backend.execute(Action("release", side="Left"))
    assert backend.buttons["Left"] == {1}


def test_sdk_disconnect_detected_when_camera_is_idle():
    fake = FakeUser32()
    backend = MouseMuxBackend(fake)
    backend.start()
    fake.running = False
    backend.pump()
    assert not backend.ready and "terputus" in backend.error


def test_two_hand_engine_emits_tagged_actions_and_no_shared_owner():
    engine = GestureEngine(Settings(independent=True, debounce=0))
    engine.update([hand(), hand("Left", dx=-0.2)], 0)
    actions = engine.update([hand(pinch=12), hand("Left", pinch=12, dx=-0.2)], 0.1)
    assert [(a.kind, a.side) for a in actions] == [
        ("left_down_at", "Right"), ("left_down_at", "Left")
    ]
    assert engine.owner is None
    actions = engine.update([hand(), hand("Left", pinch=12, dx=-0.2)], 0.2)
    assert [(a.kind, a.side) for a in actions] == [("release", "Right")]
    assert engine.states["Left"].mode == "left"
    assert engine.update([hand(), hand("Left", dx=-0.2)], 0.3) == [Action("release", side="Left")]


def test_camera_worker_defaults_to_corrected_label():
    from deskpilot.camera import CameraWorker

    worker = CameraWorker(0, "unused", lambda _: None)
    assert worker.tracker.swap is True
    worker.stop()
