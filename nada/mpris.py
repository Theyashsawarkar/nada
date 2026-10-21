"""MPRIS (org.mpris.MediaPlayer2.nada): media keys through playerctl, the
phone's media controls through KDE Connect, anything else that speaks it."""
from gi.repository import Gio, GLib

XML = """
<node>
  <interface name="org.mpris.MediaPlayer2">
    <method name="Raise"/><method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/>
    <property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/>
    <property name="Identity" type="s" access="read"/>
    <property name="DesktopEntry" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="Next"/><method name="Previous"/><method name="Pause"/>
    <method name="PlayPause"/><method name="Stop"/><method name="Play"/>
    <method name="Seek"><arg direction="in" name="Offset" type="x"/></method>
    <method name="SetPosition"><arg direction="in" name="TrackId" type="o"/><arg direction="in" name="Position" type="x"/></method>
    <method name="OpenUri"><arg direction="in" name="Uri" type="s"/></method>
    <signal name="Seeked"><arg name="Position" type="x"/></signal>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="LoopStatus" type="s" access="readwrite"/>
    <property name="Rate" type="d" access="readwrite"/>
    <property name="Shuffle" type="b" access="readwrite"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="Volume" type="d" access="readwrite"/>
    <property name="Position" type="x" access="read"/>
    <property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
  </interface>
</node>"""
ROOT, PLAYER = "org.mpris.MediaPlayer2", "org.mpris.MediaPlayer2.Player"
PATH = "/org/mpris/MediaPlayer2"


class MPRIS:
    def __init__(self, core, raise_cb, quit_cb):
        self.core, self.raise_cb, self.quit_cb = core, raise_cb, quit_cb
        self.conn = None
        self.last = {}
        self.node = Gio.DBusNodeInfo.new_for_xml(XML)
        Gio.bus_own_name(Gio.BusType.SESSION, "org.mpris.MediaPlayer2.nada", Gio.BusNameOwnerFlags.NONE,
                         self._acquired, None, None)
        core.listen(self._changed)

    def _acquired(self, conn, name):
        self.conn = conn
        for iface in self.node.interfaces:
            conn.register_object(PATH, iface, self._call, self._get, self._set)

    # ------------------------------------------------------------ values
    def _metadata(self):
        s = self.core.current
        if not s:
            return {"mpris:trackid": GLib.Variant("o", "/org/mpris/MediaPlayer2/TrackList/NoTrack")}
        md = {
            "mpris:trackid": GLib.Variant("o", f"/dev/vayu/Nada/track/{s['id']}"),
            "mpris:length": GLib.Variant("x", int((self.core.duration() or 0) * 1e6)),
            "xesam:title": GLib.Variant("s", s["title"] or ""),
            "xesam:artist": GLib.Variant("as", [a for a in [s["artist"]] if a]),
            "xesam:album": GLib.Variant("s", s["album"] or ""),
            "xesam:url": GLib.Variant("s", s["file"] if s["stream"] else "file://" + s["file"]),
        }
        art = self.core.art.get("path")
        if art and self.core.art.get("for") == s["id"]:
            md["mpris:artUrl"] = GLib.Variant("s", "file://" + art)
        return md

    def _status(self):
        return {"play": "Playing", "pause": "Paused"}.get(self.core.state, "Stopped")

    def _props(self, iface):
        c = self.core
        if iface == ROOT:
            return {"CanQuit": GLib.Variant("b", True), "CanRaise": GLib.Variant("b", True),
                    "HasTrackList": GLib.Variant("b", False), "Identity": GLib.Variant("s", "nāda"),
                    "DesktopEntry": GLib.Variant("s", "nada"),
                    "SupportedUriSchemes": GLib.Variant("as", ["file", "http", "https"]),
                    "SupportedMimeTypes": GLib.Variant("as", ["audio/mpeg", "audio/ogg", "audio/flac", "audio/opus"])}
        p = c.cur_pos
        loop = {"off": "None", "all": "Playlist", "one": "Track"}[c.repeat_mode()]
        vol = c.volume
        return {"PlaybackStatus": GLib.Variant("s", self._status()), "LoopStatus": GLib.Variant("s", loop),
                "Rate": GLib.Variant("d", 1.0), "MinimumRate": GLib.Variant("d", 1.0), "MaximumRate": GLib.Variant("d", 1.0),
                "Shuffle": GLib.Variant("b", c.status.get("random") == "1"),
                "Metadata": GLib.Variant("a{sv}", self._metadata()),
                "Volume": GLib.Variant("d", max(0, vol) / 100), "Position": GLib.Variant("x", int(c.elapsed() * 1e6)),
                "CanGoNext": GLib.Variant("b", 0 <= p < len(c.queue) - 1),
                "CanGoPrevious": GLib.Variant("b", p > 0 or c.elapsed() > 4),
                "CanPlay": GLib.Variant("b", bool(c.queue)), "CanPause": GLib.Variant("b", bool(c.queue)),
                "CanSeek": GLib.Variant("b", c.current is not None), "CanControl": GLib.Variant("b", True)}

    # ------------------------------------------------------------ D-Bus
    def _get(self, conn, sender, path, iface, prop):
        return self._props(iface).get(prop)

    def _set(self, conn, sender, path, iface, prop, value):
        c, v = self.core, value.unpack()
        if prop == "Volume":
            c.set_volume(v * 100)
        elif prop == "Shuffle":
            if v != (c.status.get("random") == "1"):
                c.toggle_random()
        elif prop == "LoopStatus":
            c.cmd("repeat", "0" if v == "None" else "1")
            c.cmd("single", "1" if v == "Track" else "0")
        return True

    def _call(self, conn, sender, path, iface, method, params, inv):
        c = self.core
        args = params.unpack()
        if method == "Raise":
            self.raise_cb()
        elif method == "Quit":
            self.quit_cb()
        elif method == "PlayPause":
            c.toggle()
        elif method == "Play":
            if c.state != "play":
                c.toggle()
        elif method == "Pause":
            if c.state == "play":
                c.cmd("pause", "1")
        elif method == "Stop":
            c.cmd("stop")
        elif method == "Next":
            c.next()
        elif method == "Previous":
            c.prev()
        elif method == "Seek":
            c.seek(args[0] / 1e6)
        elif method == "SetPosition":
            c.seek_to(args[1] / 1e6)
        elif method == "OpenUri":
            c.add_url(args[0], "play")
        inv.return_value(None)

    def _changed(self, event):
        if self.conn is None or isinstance(event, tuple):
            return
        if event not in ("player", "song", "art", "mixer", "options", "queue"):
            return
        props = self._props(PLAYER)
        props.pop("Position")
        changed = {k: v for k, v in props.items() if self.last.get(k) != v.print_(False)}
        self.last.update({k: v.print_(False) for k, v in changed.items()})
        if changed:
            self.conn.emit_signal(None, PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                                  GLib.Variant("(sa{sv}as)", (PLAYER, changed, [])))
        if event == "player":
            self.conn.emit_signal(None, PATH, PLAYER, "Seeked", GLib.Variant("(x)", (int(self.core.elapsed() * 1e6),)))
