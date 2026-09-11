"""Portal protocol tests without assuming an actual Wayland compositor."""

import asyncio
import threading

import pytest
from dbus_next import Message, Variant

from deskpilot.backends.portal import PortalBackend


class FakeBus:
    unique_name = ":1.42"

    def __init__(self):
        self.handlers = []

    def add_message_handler(self, handler):
        self.handlers.append(handler)

    def remove_message_handler(self, handler):
        self.handlers.remove(handler)


def test_request_catches_response_before_method_returns():
    b = PortalBackend()
    b.loop = asyncio.new_event_loop()
    b.bus = FakeBus()

    async def call(interface, member, signature="", body=None, path=None):
        token = body[-1]["handle_token"].value
        message = Message.new_signal(
            f"/org/freedesktop/portal/desktop/request/1_42/{token}",
            "org.freedesktop.portal.Request",
            "Response",
            "ua{sv}",
            [0, {"session_handle": Variant("s", "/session/ok")}],
        )
        for handler in b.bus.handlers:
            handler(message)
        return [message.path]

    b._call = call
    try:
        result = b.loop.run_until_complete(b._request("interface", "CreateSession", "a{sv}", [], {}))
        assert result["session_handle"].value == "/session/ok"
        assert not b.bus.handlers
    finally:
        b.loop.close()


def test_cancel_closes_pending_request_and_removes_subscription():
    b = PortalBackend()
    b.loop = asyncio.new_event_loop()
    b.bus = FakeBus()
    b.cancel_event = threading.Event()
    b.cancel_event.set()
    calls = []

    async def call(interface, member, signature="", body=None, path=None):
        calls.append(member)
        return ["/pending"]

    b._call = call
    try:
        with pytest.raises(RuntimeError, match="dibatalkan"):
            b.loop.run_until_complete(b._request("interface", "Start", "osa{sv}", ["/session", ""], {}))
        assert calls == ["Start", "Close"]
        assert not b.bus.handlers
    finally:
        b.loop.close()


def test_absolute_input_clamps_and_uses_stream_local_coordinates():
    b = PortalBackend()
    b.width, b.height, b.stream = 1280, 720, 17
    calls = []
    b._notify = lambda *args: calls.append(args)
    b.absolute(-0.2, 1.2)
    assert calls == [("NotifyPointerMotionAbsolute", "udd", [17, 0.0, 719.0])]
    b.button(4, True)
    b.button(4, False)
    assert calls[-1] == ("NotifyPointerAxisDiscrete", "ui", [0, -1])
