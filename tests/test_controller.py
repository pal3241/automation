import time

from test_gestures import hand

from deskpilot.backends.base import PreviewBackend
from deskpilot.controller import Controller


def wait_until(predicate, timeout=2):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def test_watchdog_releases_held_input(monkeypatch):
    b = PreviewBackend()
    monkeypatch.setattr("deskpilot.controller.create_backend", lambda choice: b)
    c = Controller()
    c.start()
    try:
        wait_until(lambda: c.ready)
        c.arm(True)
        c.submit([hand()])
        time.sleep(0.05)
        c.submit([hand(pinch=16)])
        wait_until(lambda: bool(b.held_buttons))
        wait_until(lambda: not b.held_buttons, 1)
        assert not b.held_keys
    finally:
        c.stop()
        c.join(2)
    assert not c.is_alive()


def test_pause_clears_pending_input(monkeypatch):
    b = PreviewBackend()
    monkeypatch.setattr("deskpilot.controller.create_backend", lambda choice: b)
    c = Controller()
    c.start()
    try:
        wait_until(lambda: c.ready)
        c.arm(True)
        c.submit([hand(pinch=12)])
        c.arm(False)
        wait_until(lambda: not c.enabled)
        time.sleep(0.1)
        assert not any(event[:2] == ("button", 1) for event in b.events)
    finally:
        c.stop()
        c.join(2)
