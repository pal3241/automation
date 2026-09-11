"""Wayland RemoteDesktop + ScreenCast portal, Notify API (no root/uinput).

Session approval runs in the executor thread. Subscribe before each request to
avoid fast-response races. Only a single monitor is selected for absolute input.
"""

import asyncio
import uuid

from .base import DesktopBackend

SERVICE = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
REMOTE = "org.freedesktop.portal.RemoteDesktop"
CAST = "org.freedesktop.portal.ScreenCast"


class PortalBackend(DesktopBackend):
    name = "Wayland • XDG RemoteDesktop"

    def start(self):
        self.loop = asyncio.new_event_loop()
        self.bus = None
        self.session = None
        try:
            self.loop.run_until_complete(self._start())
            self.ready = True
        except Exception:
            self.close()
            raise

    async def _call(self, interface, member, signature="", body=None, path=PATH):
        from dbus_next import Message, MessageType

        reply = await asyncio.wait_for(
            self.bus.call(
                Message(
                    destination=SERVICE,
                    path=path,
                    interface=interface,
                    member=member,
                    signature=signature,
                    body=body or [],
                )
            ),
            10,
        )
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"{member}: {reply.body}")
        return reply.body

    async def _request(self, interface, member, signature, body, options):
        from dbus_next import MessageType, Variant

        token = "deskpilot_" + uuid.uuid4().hex
        options = dict(options, handle_token=Variant("s", token))
        sender = self.bus.unique_name[1:].replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        future = self.loop.create_future()

        def response(message):
            if (
                message.message_type == MessageType.SIGNAL
                and message.path == path
                and message.interface == "org.freedesktop.portal.Request"
                and message.member == "Response"
                and not future.done()
            ):
                future.set_result(message.body)

        self.bus.add_message_handler(response)
        try:
            await self._call(interface, member, signature, [*body, options])
            deadline = self.loop.time() + 120
            while not future.done():
                if getattr(self, "cancel_event", None) and self.cancel_event.is_set():
                    raise RuntimeError("Koneksi desktop dibatalkan")
                if self.loop.time() >= deadline:
                    raise TimeoutError("Dialog izin desktop melewati batas 120 detik")
                await asyncio.wait({future}, timeout=0.1)
            code, results = future.result()
            if code != 0:
                raise RuntimeError("Izin kontrol layar dibatalkan atau ditolak")
            return results
        except BaseException:
            try:
                await self._call("org.freedesktop.portal.Request", "Close", path=path)
            except Exception:
                pass
            raise
        finally:
            self.bus.remove_message_handler(response)

    async def _start(self):
        from dbus_next import Message, Variant
        from dbus_next.aio import MessageBus

        self.bus = await MessageBus().connect()
        reply = await self.bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="AddMatch",
                signature="s",
                body=["type='signal',interface='org.freedesktop.portal.Request'"],
            )
        )
        if reply.error_name:
            raise RuntimeError(str(reply.body))
        reply = await self.bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="AddMatch",
                signature="s",
                body=["type='signal',interface='org.freedesktop.portal.Session'"],
            )
        )
        if reply.error_name:
            raise RuntimeError(str(reply.body))
        result = await self._request(
            REMOTE,
            "CreateSession",
            "a{sv}",
            [],
            {"session_handle_token": Variant("s", "deskpilot_" + uuid.uuid4().hex)},
        )
        self.session = result["session_handle"].value

        def closed(message):
            if (
                message.path == self.session
                and message.interface == "org.freedesktop.portal.Session"
                and message.member == "Closed"
            ):
                self.ready = False
                self.error = "Sesi kontrol desktop ditutup. Hubungkan ulang."

        self.bus.add_message_handler(closed)
        await self._request(REMOTE, "SelectDevices", "oa{sv}", [self.session], {"types": Variant("u", 3)})
        await self._request(
            CAST,
            "SelectSources",
            "oa{sv}",
            [self.session],
            {"types": Variant("u", 1), "multiple": Variant("b", False)},
        )
        result = await self._request(REMOTE, "Start", "osa{sv}", [self.session, ""], {})
        if result.get("devices") is None or result["devices"].value & 3 != 3:
            raise RuntimeError("Kontrol membutuhkan izin keyboard dan pointer")
        streams = result.get("streams")
        if not streams or not streams.value:
            raise RuntimeError("Pilih satu monitor untuk pemetaan tangan ke layar")
        self.stream, metadata = streams.value[0]
        size = metadata.get("size")
        if not size or min(size.value) <= 0:
            raise RuntimeError("Portal tidak memberikan ukuran monitor untuk klik absolut")
        self.width, self.height = size.value

    def _notify(self, member, signature, body):
        self.loop.run_until_complete(
            self._call(REMOTE, member, "oa{sv}" + signature, [self.session, {}, *body])
        )

    def pump(self):
        if hasattr(self, "loop") and not self.loop.is_closed():
            self.loop.run_until_complete(asyncio.sleep(0))

    def absolute(self, x, y):
        self._notify(
            "NotifyPointerMotionAbsolute",
            "udd",
            [
                self.stream,
                float(max(0, min(1, x)) * (self.width - 1)),
                float(max(0, min(1, y)) * (self.height - 1)),
            ],
        )

    def relative(self, dx, dy):
        self._notify("NotifyPointerMotion", "dd", [float(dx), float(dy)])

    def button(self, button, down):
        if button in (4, 5):
            if down:
                self._notify("NotifyPointerAxisDiscrete", "ui", [0, -1 if button == 4 else 1])
        else:
            self._notify("NotifyPointerButton", "iu", [{1: 272, 2: 274, 3: 273}[button], int(down)])

    def key(self, key, down):
        keysym = {"Control_L": 0xFFE3, "Super_L": 0xFFEB, "Alt_L": 0xFFE9}[key]
        self._notify("NotifyKeyboardKeysym", "iu", [keysym, int(down)])

    def close(self):
        try:
            super().close()
        finally:
            if getattr(self, "session", None):
                try:
                    self.loop.run_until_complete(
                        self._call("org.freedesktop.portal.Session", "Close", path=self.session)
                    )
                except Exception:
                    pass
                self.session = None
            if getattr(self, "bus", None):
                self.bus.disconnect()
            if hasattr(self, "loop") and not self.loop.is_closed():
                self.loop.close()
