#!/usr/bin/env python3
"""Firefox native messaging <-> a dedicated YouTube Music MPRIS player."""
# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import hashlib
import json
import math
import os
import struct
import sys

from dbus_next import DBusError, Variant
from dbus_next.aio import MessageBus
from dbus_next.constants import NameFlag, PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method, signal

PATH = "/org/mpris/MediaPlayer2"
BUS_PREFIX = "org.mpris.MediaPlayer2.gibi_youtube_music.instance"
MAX_MESSAGE = 1024 * 1024


def finite(value, default=0.0):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value) if math.isfinite(value) else default


def clean_state(raw):
    if not isinstance(raw, dict) or raw.get("available") is not True:
        return {"available": False}
    if type(raw.get("tabId")) is not int or raw["tabId"] < 0:
        return {"available": False}
    volume = raw.get("volume")
    if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not math.isfinite(volume):
        return {"available": False}
    url = str(raw.get("url", ""))[:4096]
    if url != "https://music.youtube.com" and not url.startswith("https://music.youtube.com/"):
        return {"available": False}
    state = {"available": True, "tabId": raw["tabId"], "url": url}
    for key in ("title", "artist", "album", "artUrl"):
        state[key] = str(raw.get(key, ""))[:4096]
    if not state["artUrl"].startswith("https://"):
        state["artUrl"] = ""
    state["volume"] = max(0.0, min(1.0, finite(raw.get("volume"))))
    state["duration"] = min(1e9, max(0.0, finite(raw.get("duration"))))
    state["position"] = min(state["duration"], max(0.0, finite(raw.get("position"))))
    state["playbackStatus"] = "Playing" if raw.get("playbackStatus") == "Playing" else "Paused"
    for key in ("muted", "canPlay", "canPause", "canSeek", "canGoNext", "canGoPrevious", "seeked"):
        state[key] = raw.get(key) is True
    return state


def write_message(message, output=None):
    output = sys.stdout.buffer if output is None else output
    body = json.dumps(message, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(body) > MAX_MESSAGE:
        raise ValueError("Native message too large")
    output.write(struct.pack("=I", len(body)) + body)
    output.flush()


async def read_message(reader):
    size = struct.unpack("=I", await reader.readexactly(4))[0]
    if not 0 < size <= MAX_MESSAGE:
        raise ValueError("Invalid native message size")
    return json.loads(await reader.readexactly(size))


class RootInterface(ServiceInterface):
    def __init__(self, bridge):
        super().__init__("org.mpris.MediaPlayer2")
        self.bridge = bridge

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> 's':
        return "YouTube Music tab (Firefox)"

    @dbus_property(access=PropertyAccess.READ)
    def DesktopEntry(self) -> 's':
        return "firefox"

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> 'b':
        return self.bridge.available

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> 'b':
        return False

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> 'b':
        return False

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> 'as':
        return ["https"]

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> 'as':
        return []

    @method()
    def Raise(self):
        self.bridge.command("raise")


class PlayerInterface(ServiceInterface):
    def __init__(self, bridge):
        super().__init__("org.mpris.MediaPlayer2.Player")
        self.bridge = bridge

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> 's':
        return self.bridge.state.get("playbackStatus", "Stopped")

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> 'a{sv}':
        state = self.bridge.state
        if not self.bridge.available:
            return {}
        key = hashlib.sha256(state["url"].encode()).hexdigest()[:24]
        metadata = {
            "mpris:trackid": Variant('o', "/com/gibi/youtubemusic/track/" + key),
            "mpris:length": Variant('x', int(state["duration"] * 1_000_000)),
            "xesam:url": Variant('s', state["url"]),
            "xesam:title": Variant('s', state["title"]),
            "xesam:artist": Variant('as', [state["artist"]] if state["artist"] else []),
            "xesam:album": Variant('s', state["album"]),
        }
        if state["artUrl"]:
            metadata["mpris:artUrl"] = Variant('s', state["artUrl"])
        return metadata

    @dbus_property()
    def Volume(self) -> 'd':
        return 0.0 if self.bridge.state.get("muted") else self.bridge.state.get("volume", 0.0)

    @Volume.setter
    def Volume(self, value: 'd'):
        if not math.isfinite(value):
            raise DBusError("org.freedesktop.DBus.Error.InvalidArgs", "Volume must be finite")
        self.bridge.command("volume", max(0.0, min(1.0, value)))

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> 'x':
        return int(self.bridge.state.get("position", 0) * 1_000_000)

    @dbus_property()
    def Rate(self) -> 'd':
        return 1.0

    @Rate.setter
    def Rate(self, value: 'd'):
        if value != 1.0:
            raise DBusError("org.freedesktop.DBus.Error.NotSupported", "Playback rate is fixed")

    @dbus_property(access=PropertyAccess.READ)
    def MinimumRate(self) -> 'd':
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def MaximumRate(self) -> 'd':
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> 'b':
        return self.bridge.available

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> 'b':
        return self.bridge.state.get("canPlay", False)

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> 'b':
        return self.bridge.state.get("canPause", False)

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> 'b':
        return self.bridge.state.get("canSeek", False)

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> 'b':
        return self.bridge.state.get("canGoNext", False)

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> 'b':
        return self.bridge.state.get("canGoPrevious", False)

    @method()
    def Play(self):
        self.bridge.command("play")

    @method()
    def Pause(self):
        self.bridge.command("pause")

    @method()
    def PlayPause(self):
        self.bridge.command("toggle")

    @method()
    def Stop(self):
        self.bridge.command("pause")

    @method()
    def Next(self):
        self.bridge.command("next")

    @method()
    def Previous(self):
        self.bridge.command("previous")

    @method()
    def Seek(self, offset: 'x'):
        self.bridge.command("seek", max(0, (self.Position + offset) / 1_000_000))

    @method()
    def SetPosition(self, track_id: 'o', position: 'x'):
        if self.bridge.available and track_id == self.Metadata["mpris:trackid"].value:
            self.bridge.command("seek", max(0, position / 1_000_000))

    @signal()
    def Seeked(self, position) -> 'x':
        return position

    def properties(self):
        names = ("PlaybackStatus", "Metadata", "Volume", "CanControl", "CanPlay",
                 "CanPause", "CanSeek", "CanGoNext", "CanGoPrevious")
        return {name: getattr(self, name) for name in names}


class Bridge:
    def __init__(self, bus, output=None):
        self.bus = bus
        self.output = output
        self.name = BUS_PREFIX + str(os.getpid())
        self.owned = False
        self.state = {"available": False}
        self.root = RootInterface(self)
        self.player = PlayerInterface(self)
        bus.export(PATH, self.root)
        bus.export(PATH, self.player)

    @property
    def available(self):
        return self.state.get("available", False)

    def command(self, command, value=None):
        if not self.available:
            raise DBusError("org.freedesktop.DBus.Error.NotSupported", "YouTube Music tab is disconnected")
        write_message({"type": "command", "command": command, "value": value,
                       "tabId": self.state["tabId"]}, self.output)

    async def update(self, raw):
        old = self.player.properties()
        self.state = clean_state(raw)
        if self.available and not self.owned:
            await self.bus.request_name(self.name, NameFlag.DO_NOT_QUEUE)
            self.owned = True
        elif not self.available and self.owned:
            await self.bus.release_name(self.name)
            self.owned = False
        if self.owned:
            changed = {key: value for key, value in self.player.properties().items() if value != old[key]}
            if changed:
                self.player.emit_properties_changed(changed)
            if self.state.get("seeked"):
                self.player.Seeked(self.player.Position)


async def main():
    bus = await MessageBus().connect()
    bridge = Bridge(bus)
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    transport, _ = await asyncio.get_running_loop().connect_read_pipe(lambda: protocol, sys.stdin.buffer)
    try:
        while True:
            message = await read_message(reader)
            if isinstance(message, dict) and message.get("type") == "state":
                await bridge.update(message.get("state"))
    except asyncio.IncompleteReadError:
        pass  # Firefox closes stdin when the extension disconnects.
    finally:
        transport.close()
        bus.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        # stdout belongs exclusively to the native messaging protocol.
        print("YouTube Music bridge: " + str(error), file=sys.stderr)
        sys.exit(1)
