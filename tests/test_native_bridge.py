"""Run with dbus-run-session -- python -m unittest discover -s tests -v."""
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import struct
import sys
import unittest

from dbus_next import Variant
from dbus_next.aio import MessageBus

HOST = Path(__file__).resolve().parents[1] / "browser-bridge/native_host.py"
spec = importlib.util.spec_from_file_location("native_host", HOST)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
PLAYER = "org.mpris.MediaPlayer2.Player"


def state(volume=0.75):
    return {"available": True, "tabId": 42, "url": "https://music.youtube.com/watch?v=abc",
            "volume": volume, "muted": False, "title": "A song 🎵", "artist": "Artist",
            "duration": 200, "position": 10, "canPlay": True, "canPause": True,
            "canSeek": True, "canGoNext": True, "playbackStatus": "Playing"}


class ValidationTests(unittest.TestCase):
    def test_untrusted_state_validation(self):
        for bad in (None, [], {**state(), "tabId": True}, {**state(), "url": "https://example.com"}):
            self.assertFalse(native.clean_state(bad)["available"])
        self.assertFalse(native.clean_state(state(math.nan))["available"])
        cleaned = native.clean_state({**state(), "position": math.inf, "artUrl": "file:///etc/passwd"})
        self.assertEqual(cleaned["position"], 0)
        self.assertEqual(cleaned["artUrl"], "")

    def test_framing_uses_utf8_byte_count(self):
        output = io.BytesIO()
        native.write_message({"title": "🎵"}, output)
        message = output.getvalue()
        self.assertEqual(struct.unpack("=I", message[:4])[0], len(message[4:]))
        self.assertEqual(json.loads(message[4:]), {"title": "🎵"})


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_fragmented_native_frames_and_size_limit(self):
        buffer = io.BytesIO()
        native.write_message({"state": state()}, buffer)
        reader = asyncio.StreamReader()
        frame = buffer.getvalue()
        async def feed():
            for index in range(0, len(frame), 3):
                reader.feed_data(frame[index:index + 3])
                await asyncio.sleep(0)
        feeder = asyncio.create_task(feed())
        self.assertEqual((await native.read_message(reader))["state"]["title"], "A song 🎵")
        await feeder
        reader = asyncio.StreamReader()
        reader.feed_data(struct.pack("=I", native.MAX_MESSAGE + 1))
        with self.assertRaises(ValueError):
            await native.read_message(reader)

    async def test_bridge_routes_values_and_releases_disconnected_tab(self):
        class Bus:
            def __init__(self):
                self.owned = set()
            def export(self, path, interface):
                # Introspection validates the decorated MPRIS signatures too.
                self.interface = interface.introspect()
            async def request_name(self, name, flags):
                self.owned.add(name)
            async def release_name(self, name):
                self.owned.remove(name)
        bus, output = Bus(), io.BytesIO()
        bridge = native.Bridge(bus, output)
        changes = []
        bridge.player.emit_properties_changed = changes.append
        await bridge.update(state())
        self.assertIn(bridge.name, bus.owned)
        bridge.player.Volume = 0.5
        # Setting the property queues an absolute command; the reported value
        # stays at the site's last acknowledgment until the site replies.
        self.assertEqual(bridge.player.Volume, 0.75)
        frame = output.getvalue()
        self.assertEqual(json.loads(frame[4:]), {
            "type": "command", "command": "volume", "value": 0.5, "tabId": 42})
        await bridge.update(state(0.5))
        self.assertEqual(bridge.player.Volume, 0.5)
        self.assertEqual(changes[-1]["Volume"], 0.5)
        await bridge.update({**state(0.5), "muted": True})
        self.assertEqual(bridge.player.Volume, 0)
        await bridge.update({"available": False})
        self.assertNotIn(bridge.name, bus.owned)
        with self.assertRaises(native.DBusError):
            bridge.player.Volume = 0.3


@unittest.skipUnless(os.environ.get("DBUS_SESSION_BUS_ADDRESS"), "Run under dbus-run-session for real D-Bus tests")
class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bus = await MessageBus().connect()
        tree = await self.bus.introspect("org.freedesktop.DBus", "/org/freedesktop/DBus")
        self.dbus = self.bus.get_proxy_object("org.freedesktop.DBus", "/org/freedesktop/DBus", tree).get_interface("org.freedesktop.DBus")
        self.process = await asyncio.create_subprocess_exec(sys.executable, str(HOST),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        self.name = native.BUS_PREFIX + str(self.process.pid)

    async def asyncTearDown(self):
        self.process.stdin.close()
        try:
            await asyncio.wait_for(self.process.wait(), 3)
        except asyncio.TimeoutError:
            self.process.kill()
            await self.process.wait()
        errors = await self.process.stderr.read()
        self.bus.disconnect()
        self.assertEqual(self.process.returncode, 0, errors.decode())

    async def send(self, raw):
        buffer = io.BytesIO()
        native.write_message({"type": "state", "state": raw}, buffer)
        self.process.stdin.write(buffer.getvalue())
        await self.process.stdin.drain()

    async def wait_for(self, predicate):
        for _ in range(200):
            if await predicate():
                return
            await asyncio.sleep(0.01)
        self.fail("Timed out waiting for bridge state")

    async def test_real_dbus_native_messages_and_reverse_sync(self):
        self.assertFalse(await self.dbus.call_name_has_owner(self.name))
        await self.send(state())
        await self.wait_for(lambda: self.dbus.call_name_has_owner(self.name))
        tree = await self.bus.introspect(self.name, native.PATH)
        proxy = self.bus.get_proxy_object(self.name, native.PATH, tree)
        properties = proxy.get_interface("org.freedesktop.DBus.Properties")
        self.assertEqual((await properties.call_get(PLAYER, "Volume")).value, 0.75)
        await properties.call_set(PLAYER, "Volume", Variant('d', 0.5))
        command = await asyncio.wait_for(native.read_message(self.process.stdout), 2)
        self.assertEqual(command, {"type": "command", "command": "volume", "value": 0.5, "tabId": 42})
        # The service reports the website's acknowledged value, not a fabricated
        # percentage. A manual site-volume change returns through the same path.
        async def volume_is(value):
            return (await properties.call_get(PLAYER, "Volume")).value == value
        await self.send(state(0.5))
        await self.wait_for(lambda: volume_is(0.5))
        await self.send(state(0.2))
        await self.wait_for(lambda: volume_is(0.2))
        await self.send({**state(), "muted": True})
        await self.wait_for(lambda: volume_is(0.0))
        metadata = (await properties.call_get(PLAYER, "Metadata")).value
        self.assertEqual(metadata["mpris:length"].value, 200_000_000)
        self.assertEqual(metadata["xesam:title"].value, "A song 🎵")
        await proxy.get_interface(PLAYER).call_set_position(metadata["mpris:trackid"].value, 25_000_000)
        command = await asyncio.wait_for(native.read_message(self.process.stdout), 2)
        self.assertEqual(command["command"], "seek")
        self.assertEqual(command["value"], 25)
        await self.send({"available": False})
        async def gone():
            return not await self.dbus.call_name_has_owner(self.name)
        await self.wait_for(gone)


if __name__ == "__main__":
    unittest.main()
