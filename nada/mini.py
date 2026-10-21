"""The mini player: a small card in a corner, on top of everything (a
layer-shell surface where the compositor has one, else a normal window)."""
from gi.repository import Gdk, GLib, Gtk

from .core import fmt_time
from .widgets import G, box, label, picture

try:
    import gi
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LayerShell
except (ValueError, ImportError):
    LayerShell = None

# keybind: Nada/mini player | Space | Toggle play / pause
# keybind: Nada/mini player | . / , | Seek forward / back 10 seconds
# keybind: Nada/mini player | > / < | Play next / previous song
# keybind: Nada/mini player | z / Enter | Switch back to the full player
# keybind: Nada/mini player | q / Esc | Close the mini player (the music keeps playing)


class Mini(Gtk.Window):
    def __init__(self, app, core):
        super().__init__(application=app, title="nāda mini")
        self.app, self.core = app, core
        self.add_css_class("nada-mini")
        self.set_default_size(460, -1)
        self.set_resizable(False)
        if LayerShell is not None and LayerShell.is_supported():
            LayerShell.init_for_window(self)
            LayerShell.set_namespace(self, "nada")
            LayerShell.set_layer(self, LayerShell.Layer.TOP)
            for e in (LayerShell.Edge.BOTTOM, LayerShell.Edge.RIGHT):
                LayerShell.set_anchor(self, e, True)
                LayerShell.set_margin(self, e, 18)
            LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.ON_DEMAND)
        self.cover = box()
        self.title = label("", "now-title")
        self.artist = label("", "now-artist")
        self.lyric = label("", "lyric dim")
        self.tcur, self.tlen = label("0:00", "time", ellipsize=False), label("0:00", "time", ellipsize=False)
        self.progress = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.progress.set_draw_value(False)
        self.progress.set_hexpand(True)
        self.progress.add_css_class("progress")
        self.progress.connect("change-value", lambda _s, _t, v: (core.seek_to(v), False)[1])
        step = lambda: core.conf["seek_step"]
        self.pp = self._btn(G["play"], core.toggle, big=True)
        ctl = box(self._btn(G["prev"], core.prev), self._btn(G["back"], lambda: core.seek(-step())), self.pp,
                  self._btn(G["fwd"], lambda: core.seek(step())), self._btn(G["next"], core.next),
                  self._btn(G["dl"], lambda: core.current and core.download(core.current)),
                  self._btn("\U000f0293", self.app.show_full), spacing=2, homogeneous=True)
        right = box(self.title, self.artist, self.lyric, box(self.tcur, self.progress, self.tlen, spacing=8), ctl,
                    vertical=True, spacing=3, hexpand=True)
        root = box(self.cover, right, spacing=14, cls="nada-root mini")
        self.set_child(root)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)
        core.listen(self._event)
        self._event(None)
        GLib.timeout_add(250, self._tick)

    def _btn(self, glyph, cb, big=False):
        b = Gtk.Button()
        b.set_child(label(glyph, ellipsize=False, xalign=0.5))
        b.add_css_class("ctl")
        if big:
            b.add_css_class("big")
        b.set_focusable(False)
        b.connect("clicked", lambda *_: cb())
        return b

    def _event(self, e):
        if isinstance(e, tuple):
            return
        c = self.core
        s = c.current
        if e in (None, "song", "art", "connection"):
            child = self.cover.get_first_child()
            if child:
                self.cover.remove(child)
            path = c.art.get("path") if s and c.art.get("for") == s["id"] else None
            pic = picture(path, 92) if path else None
            if pic is None:
                pic = label(G["note"], "cover cover-glyph", xalign=0.5, ellipsize=False)
                pic.set_size_request(92, 92)
            self.cover.append(pic)
        self.title.set_text(s["title"] if s else "Nothing playing")
        self.artist.set_text((s.get("artist") or "") if s else "")
        self.pp.get_child().set_text(G["pause"] if c.state == "play" else G["play"])
        d = c.duration()
        self.progress.set_range(0, max(1, d))
        self.tlen.set_text(fmt_time(d))

    def _tick(self):
        if not self.get_visible():
            return True
        c = self.core
        t = c.elapsed()
        self.progress.set_value(t)
        self.tcur.set_text(fmt_time(t))
        lines = c.lyrics.get("lines") or []
        txt = ""
        if c.lyrics.get("synced"):
            for lt, x in lines:
                if lt <= t + 0.15:
                    txt = x
                else:
                    break
        self.lyric.set_text(f"{G['mic']}  {txt}" if txt.strip() else "")
        self.lyric.set_visible(bool(txt.strip()))
        return True

    def _key(self, ctrl, keyval, code, state):
        name = Gdk.keyval_name(keyval)
        c = self.core
        if name == "space":
            c.toggle()
        elif name == "period":
            c.seek(c.conf["seek_step"])
        elif name == "comma":
            c.seek(-c.conf["seek_step"])
        elif name == "greater":
            c.next()
        elif name == "less":
            c.prev()
        elif name in ("z", "Return"):
            self.app.show_full()
        elif name in ("q", "Escape"):
            self.set_visible(False)
        else:
            return False
        return True
