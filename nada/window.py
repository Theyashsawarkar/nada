"""The player window: tabs, the right pane, controls, the vim mode line,
and the vim key engine: keymap.py's binds through Vyom's keys.py (counts,
sequences, the Space leader), plus visual mode, registers, : and /."""
import logging
import re

from gi.repository import Gdk, Gio, GLib, Gtk

from . import art, keymap, keys, lyrics, youtube
from .config import STATE
from .core import fmt_time
from .finder import Finder
from .leader import KeySheet, Palette, WhichKey
from .search import SearchPanel
from .views import Downloads, Home, Library, NowPane, Playlists, Queue, YouTube
from .widgets import G, box, hint, label, picture, tile

# Every key is in keymap.py (data on Vyom's keys.py); its `# keybind:`
# lines are generated there. This file runs them.
TABS = keymap.TABS
KEYNAMES = {"space": " ", "period": ".", "comma": ",", "greater": ">", "less": "<", "equal": "=", "plus": "+",
            "minus": "-", "slash": "/", "colon": ":", "question": "?", "KP_Enter": "Return", "Up": "k", "Down": "j",
            "KP_Add": "+", "KP_Subtract": "-", "BackSpace": "BackSpace", "bracketleft": "[", "bracketright": "]"}


class Window(Gtk.ApplicationWindow):
    def __init__(self, app, core):
        super().__init__(application=app, title="nāda")
        self.app, self.core = app, core
        self.add_css_class("nada")
        self.set_default_size(1180, 720)
        self.register = []
        self.m = keys.Machine()   # a count and a pending sequence between keys
        self.mode = "NORMAL"
        self.notes_shown = set()
        self.confirm_cb = None
        self.tab = "home"
        self.thumbs, self.thumb_wait = {}, set()
        self.thumb_timer = None
        self.toast_timer = None
        self.sleep_timer = None
        self.dragging = False

        overlay = Gtk.Overlay()
        self.set_child(overlay)
        self.root = box(vertical=True, cls="nada-root", focusable=True)
        overlay.set_child(self.root)

        # top bar
        self.tabbtn = {}
        top = box(spacing=4, cls="topbar")
        top.append(box(label(G["note"], "glyph", ellipsize=False), label("nāda", ellipsize=False), spacing=7, cls="logo",
                       margin_end=8))
        self.views = {}
        for i, cls in enumerate([Home, Queue, Library, Playlists, Downloads, YouTube]):
            v = cls(self)
            self.views[v.name] = v
            if v.name not in TABS:
                continue
            b = Gtk.Button()
            b.add_css_class("tab")
            # Just the name: digits are counts now (5j). H / L step through the
            # tabs, Space t picks one; the tooltip says which keys.
            b.set_child(label(v.title, ellipsize=False))
            b.set_tooltip_text(f"{v.title}: H / L step through the tabs, Ctrl+{i} jumps here")
            b.set_focusable(False)
            b.connect("clicked", lambda _b, n=v.name: self.switch(n))
            self.tabbtn[v.name] = b
            top.append(b)
        self.summary = label("", "mono dim", ellipsize=False, hexpand=True, xalign=1)
        self.modelab = label("NORMAL", "mode", ellipsize=False)
        top.append(self.summary)
        top.append(self.modelab)
        self.root.append(top)

        # body
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120,
                               hexpand=True, vexpand=True)
        for name, v in self.views.items():
            self.stack.add_named(v.widget, name)
        self.now = NowPane(self)
        self.root.append(box(self.stack, self.now, vexpand=True))

        # controls
        self.root.append(self._controls())

        # status line
        self.cmdline = Gtk.Text(hexpand=True)
        self.cmdline.add_css_class("cmdline")
        self.cmdline.connect("activate", self._cmd_activate)
        self.prefix = label("", "cmdline", ellipsize=False)
        self.msg = label("", "cmdline", hexpand=True)
        self.hints = box(spacing=14)
        self.root.append(box(self.prefix, self.cmdline, self.msg, self.hints, spacing=2, cls="status"))
        self.cmdline.set_visible(False)

        # toast + help overlays
        self.toast_lab = label("", wrap=True, max_width_chars=90)
        self.toast_rev = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.CROSSFADE, halign=Gtk.Align.CENTER,
                                      valign=Gtk.Align.END, can_target=False)
        self.toast_rev.set_child(box(self.toast_lab, cls="toast"))
        overlay.add_overlay(self.toast_rev)
        self.help = KeySheet(keymap.COMMANDS)
        overlay.add_overlay(self.help)
        # the leader: what can come next, and every action (Space Space)
        self.which = WhichKey()
        overlay.add_overlay(self.which)
        self.palette = Palette(lambda b: self.run(b.action, 1, False))
        overlay.add_overlay(self.palette)
        # the lyrics panel (L on Now): pick a version, the script, the timing
        self.lpanel = self._lyrics_panel()
        self.lpanel.set_visible(False)
        overlay.add_overlay(self.lpanel)
        # the search panel (/), over a dimmed window
        self.finder = Finder(self)
        self.scrim = Gtk.Box(hexpand=True, vexpand=True, visible=False, css_classes=["scrim"])
        g = Gtk.GestureClick()
        g.connect("pressed", lambda *_: self.close_search())
        self.scrim.add_controller(g)
        overlay.add_overlay(self.scrim)
        self.search = SearchPanel(self, self.finder, STATE, "Search songs, artists, YouTube… or :command")
        self.search.set_margin_top(64)
        self.search.set_visible(False)
        overlay.add_overlay(self.search)
        # toasts above everything, the search panel included
        overlay.remove_overlay(self.toast_rev)
        overlay.add_overlay(self.toast_rev)

        ctl = Gtk.EventControllerKey()
        ctl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        ctl.connect("key-pressed", self._key)
        self.add_controller(ctl)
        self.connect("close-request", lambda *_: (self.hide_window(), True)[1])
        self.connect("notify::visible", lambda *_: setattr(self.core, "window_visible", self.get_visible()))

        core.listen(self._core_event)
        for v in self.views.values():
            v.refresh(None)
        self.now.refresh(None)
        self._update_controls()
        self._bar_now()
        self.switch("home")
        GLib.timeout_add(200, self._tick)

    # ------------------------------------------------------------ building
    def _btn(self, glyph, tip, cb, big=False):
        b = Gtk.Button(tooltip_text=tip, valign=Gtk.Align.CENTER)
        b.set_child(label(glyph, ellipsize=False, xalign=0.5))
        b.add_css_class("ctl")
        if big:
            b.add_css_class("big")
        b.set_focusable(False)
        b.connect("clicked", lambda *_: cb())
        return b

    def _controls(self):
        """One row under a thin timeline: what's playing on the left, the
        controls in the middle, time and volume on the right."""
        c = self.core
        step = lambda: c.conf["seek_step"]
        self.pp = self._btn(G["play"], "Play / pause  (p)", c.toggle, big=True)
        self.shuf = self._btn(G["shuffle"], "Shuffle  (Space p s)", c.toggle_random)
        self.rep = self._btn(G["repeat"], "Repeat: off, all, this song  (Space p r)", c.cycle_repeat)
        ctl = box(self.shuf, self._btn(G["prev"], "Previous song  (<)", c.prev),
                  self._btn(G["back"], "Back 10 seconds  (,)", lambda: c.seek(-step())), self.pp,
                  self._btn(G["fwd"], "Forward 10 seconds  (.)", lambda: c.seek(step())),
                  self._btn(G["next"], "Next song  (>)", c.next), self.rep, spacing=4, halign=Gtk.Align.CENTER)
        self.bar_art = box(valign=Gtk.Align.CENTER)
        self.bar_title = label("", "bar-title")
        self.bar_sub = label("", "bar-sub")
        left = box(self.bar_art, box(self.bar_title, self.bar_sub, vertical=True, valign=Gtk.Align.CENTER, hexpand=True),
                   spacing=10)
        left.set_size_request(300, -1)
        self.tcur = label("0:00", "time", ellipsize=False)
        self.tlen = label("0:00", "time", ellipsize=False)
        self.volglyph = self._btn(G["vol"], "Mute  (m)", c.mute)
        self.vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol.set_draw_value(False)
        self.vol.set_size_request(86, -1)
        self.vol.add_css_class("volume")
        self.vol.set_focusable(False)
        self.vol.connect("change-value", lambda _s, _t, v: (c.set_volume(v), False)[1])
        self.volv = label("", "time", ellipsize=False)
        self.volv.set_size_request(26, -1)
        right = box(self.tcur, label("/", "time", ellipsize=False), self.tlen, label("", margin_start=8), self.volglyph,
                    self.vol, self.volv, spacing=4, halign=Gtk.Align.END)
        right.set_size_request(300, -1)
        row = Gtk.CenterBox(start_widget=left, center_widget=ctl, end_widget=right)
        row.add_css_class("bar-row")
        self.progress = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.progress.set_draw_value(False)
        self.progress.set_hexpand(True)
        self.progress.add_css_class("progress")
        self.progress.add_css_class("slim")
        self.progress.set_focusable(False)
        self.progress.connect("change-value", self._seek_drag)
        return box(self.progress, row, vertical=True, cls="bar")

    def _bar_now(self):
        """The bar's left side: the cover, the song's real name and artists."""
        c = self.core
        s = c.current
        child = self.bar_art.get_first_child()
        if child:
            self.bar_art.remove(child)
        if not s:
            self.bar_title.set_text("Nothing playing")
            self.bar_sub.set_text("/ to search")
            self.bar_art.append(label(G["note"], "glyph bar-glyph", xalign=0.5, ellipsize=False))
            return
        m = c.lyrics.get("meta") if c.lyrics.get("for") == s["id"] else None
        self.bar_title.set_text((m or {}).get("title") or s["title"])
        self.bar_sub.set_text(", ".join((m or {}).get("artists") or []) or s.get("artist") or s.get("channel") or "")
        path = c.art.get("path") if c.art.get("for") == s["id"] else None
        self.bar_art.append((picture(path, 42, "tile") if path else None) or tile(s.get("yt") or s.get("file"), s["title"], 42))

    # ------------------------------------------------------------ search panel (/)
    def open_search(self, text="", scope=0):
        if self.lpanel.get_visible():
            self._lp_close()
        self.scrim.set_visible(True)
        self.search.open(text, scope)
        self.set_mode("SEARCH")

    def close_search(self):
        self.search.close()
        self.scrim.set_visible(False)
        self.root.grab_focus()
        self.set_mode("NORMAL")

    # ------------------------------------------------------------ lyrics panel (L)
    def _lyrics_panel(self):
        self.lp_title = label("Lyrics", "menu-title")
        self.lp_chips = box(spacing=6, cls="lp-chips")
        self.lp_note = label("", "dim menu-note", wrap=True, max_width_chars=48)
        self.lp_list = box(vertical=True, spacing=4)
        sc = Gtk.ScrolledWindow(vexpand=True, propagate_natural_height=True, max_content_height=440)
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.add_css_class("noscrollbar")
        sc.set_child(self.lp_list)
        self.lp_scroll = sc
        foot = box(hint("j k", "move"), hint("Enter", "use"), hint("s", "script"), hint("[ ]", "timing"),
                   hint("Esc", "close"), spacing=12, cls="menu-foot")
        self.lp_items, self.lp_sel = [], 0
        return box(self.lp_title, self.lp_chips, self.lp_note, sc, foot, vertical=True, spacing=6, cls="menu lpanel",
                   halign=Gtk.Align.END, valign=Gtk.Align.START, margin_top=70, margin_end=24, margin_bottom=110)

    def open_lyrics_panel(self):
        c = self.core
        if not c.current:
            self.toast("Nothing playing")
            return
        self.lpanel.set_visible(True)
        self.set_mode("LYRICS")
        m = c.lyrics.get("meta") or {}
        self.lp_title.set_text(f"Lyrics for {m.get('title') or c.current['title']}")
        self._lp_chips()
        self.lp_items, self.lp_sel = [], 0
        self._lp_list()
        self.lp_note.set_text("Asking YouTube Music, LRCLIB and NetEase…")
        self.lp_note.set_visible(True)

        def got(cands):
            if self.lpanel.get_visible():
                self.lp_items = cands
                self.lp_sel = 0
                self.lp_note.set_text("" if cands else "No source has lyrics for this song. :lyrics <words> searches LRCLIB "
                                                         "with your own words.")
                self.lp_note.set_visible(not cands)
                self._lp_list()
        c.lyrics_candidates(got)

    def _lp_chips(self):
        c = self.core
        child = self.lp_chips.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.lp_chips.remove(child)
            child = nxt
        latin = c.lyrics_script == "latin"
        self.lp_chips.append(label("Hinglish", "chip act" if latin else "chip", ellipsize=False))
        self.lp_chips.append(label("हिन्दी", "chip" if latin else "chip act", ellipsize=False))
        self.lp_chips.append(Gtk.Box(hexpand=True))
        off = c.lyrics.get("offset") or 0.0
        self.lp_chips.append(label(f"timing {off:+.2f} s", "chip act" if off else "chip", ellipsize=False))

    def _lp_list(self):
        child = self.lp_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.lp_list.remove(child)
            child = nxt
        self.lp_rows = []
        for i, cand in enumerate(self.lp_items):
            head = box(label(cand["source"], "cand-source", hexpand=True), spacing=6)
            if cand.get("in_use"):
                head.append(label("in use", "chip ok", ellipsize=False))
            head.append(label("synced" if cand["synced"] else "plain", "chip ok" if cand["synced"] else "chip",
                              ellipsize=False))
            diff = cand.get("diff") or 0
            fit = ("same length" if diff <= 8 else f"{int(diff // 60)}:{int(diff % 60):02d} {'longer' if (cand.get('duration') or 0) > (self.core.duration() or 0) else 'shorter'}") \
                if cand.get("duration") else ""
            who = " · ".join(x for x in (cand.get("title"), cand.get("artist"), fit) if x)
            first = lyrics.in_script("\n".join(cand.get("first") or []), self.core.lyrics_script)
            w = box(head, label(who, "cand-fit" + (" off" if diff > 8 else "")), label(first, "cand-first", wrap=True,
                                                                                        max_width_chars=50),
                    vertical=True, spacing=3, cls="cand")
            g = Gtk.GestureClick()
            g.connect("pressed", lambda _g, n, *_a, i=i: (setattr(self, "lp_sel", i), self._lp_paint(),
                                                          n == 2 and self._lp_use()))
            w.add_controller(g)
            self.lp_rows.append(w)
            self.lp_list.append(w)
        self._lp_paint()

    def _lp_paint(self):
        for i, w in enumerate(getattr(self, "lp_rows", [])):
            (w.add_css_class if i == self.lp_sel else w.remove_css_class)("sel")

    def _lp_use(self):
        if 0 <= self.lp_sel < len(self.lp_items):
            cand = self.lp_items[self.lp_sel]
            self.core.use_lyrics(cand)
            for c2 in self.lp_items:
                c2["in_use"] = c2 is cand
            self._lp_list()
            self.toast(f"Using {cand['source']}'s lyrics · kept for this song")

    def _lp_close(self):
        self.lpanel.set_visible(False)
        self.root.grab_focus()
        self.set_mode("NORMAL")

    def _lp_key(self, name):
        c = self.core
        if name in ("Escape", "L", "q"):
            self._lp_close()
        elif name in ("j", "Down") and self.lp_items:
            self.lp_sel = min(len(self.lp_items) - 1, self.lp_sel + 1)
            self._lp_paint()
        elif name in ("k", "Up") and self.lp_items:
            self.lp_sel = max(0, self.lp_sel - 1)
            self._lp_paint()
        elif name in ("Return", "KP_Enter", "l"):
            self._lp_use()
        elif name == "s":
            c.set_lyrics_script("native" if c.lyrics_script == "latin" else "latin")
            self.toast("Lyrics in Latin letters (Hinglish)" if c.lyrics_script == "latin" else "Lyrics as written (Devanagari)")
            GLib.timeout_add(400, lambda: (self._lp_chips(), False)[1])
        elif name in ("bracketleft", "bracketright"):
            off = c.nudge_lyrics(-0.25 if name == "bracketleft" else 0.25)
            self.toast(f"Lyrics {'earlier' if name == 'bracketleft' else 'later'}: {off:+.2f} s · kept for this song")
            GLib.timeout_add(300, lambda: (self._lp_chips(), False)[1])
        return True

    # ------------------------------------------------------------ tabs
    def switch(self, name):
        if name not in self.views:
            return
        cur = self.views.get(self.tab)
        if cur and cur.list() is not None and cur.list().vstart is not None:
            cur.list().visual(False)
        self.tab = name
        self.stack.set_visible_child_name(name)
        for n, b in self.tabbtn.items():
            (b.add_css_class if n == name else b.remove_css_class)("on")
        self.now.set_home(name == "home")
        if name == "home":
            self.now.set_page("now")
        self.views[name].shown()
        self.drop_pending()
        self.set_mode("NORMAL")
        self._hints()
        if self.cmdline.get_visible():
            self._cmd_close()

    def drop_pending(self):
        """Another tab (or the window hidden): what was waiting goes. A key
        sequence or count, an unanswered question (else a y on the new tab
        would answer it), the palette and key sheet of the old tab."""
        self.m.reset()
        self.which.cancel()
        self.confirm_cb = None
        self._show_pending()
        self.palette.close()
        self.help.set_visible(False)

    def toggle_lyrics(self):
        if self.tab == "home":
            self.toast("Now already shows the lyrics · L for the queue")
            return
        page = "now" if self.now.stack.get_visible_child_name() == "lyrics" else "lyrics"
        self.now.set_page(page)
        if page == "lyrics":
            self.now.lyrics.cur = -2
            self.now.lyrics.update(self.core.elapsed())

    # ------------------------------------------------------------ status line
    def set_mode(self, mode):
        self.mode = mode
        self.modelab.set_text(mode)
        for m in ("visual", "search", "command", "confirm", "lyrics"):
            (self.modelab.add_css_class if mode.lower() == m else self.modelab.remove_css_class)(m)

    def _hints(self):
        child = self.hints.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.hints.remove(child)
            child = nxt
        for k, w in self.views[self.tab].hints + [("?", "all keys")]:
            self.hints.append(hint(k, w))

    def _show_pending(self):
        self.msg.set_text(self.m.typed())

    def toast(self, text):
        self.toast_lab.set_text(text)
        self.toast_rev.set_reveal_child(True)
        if self.toast_timer:
            GLib.source_remove(self.toast_timer)
        self.toast_timer = GLib.timeout_add(2600, self._toast_hide)

    def _toast_hide(self):
        self.toast_rev.set_reveal_child(False)
        self.toast_timer = None
        return False

    def confirm(self, question, cb):
        self.confirm_cb = cb
        self.set_mode("CONFIRM")
        self.msg.set_text(f"{question}  y yes · any other key no")

    # ------------------------------------------------------------ core events
    def _core_event(self, e):
        if isinstance(e, tuple):
            if e[0] == "toast":
                self.toast(e[1])
            return
        for v in self.views.values():
            v.refresh(e)
        self.now.refresh(e)
        if e in ("player", "mixer", "options", "song", "queue", "connection"):
            self._update_controls()
        if e in ("song", "art", "lyrics", "connection"):
            self._bar_now()

    def _update_controls(self):
        c = self.core
        playing = c.state == "play"
        self.pp.get_child().set_text(G["pause"] if playing else G["play"])
        (self.shuf.add_css_class if c.status.get("random") == "1" else self.shuf.remove_css_class)("on")
        rep = c.repeat_mode()
        self.rep.get_child().set_text({"off": G["repeat_off"], "all": G["repeat"], "one": G["repeat_one"]}[rep])
        (self.rep.add_css_class if rep != "off" else self.rep.remove_css_class)("on")
        v = c.volume
        self.vol.set_sensitive(v >= 0)
        if v >= 0:
            self.vol.set_value(v)
        self.volv.set_text(str(v) if v >= 0 else "–")
        self.volglyph.get_child().set_text(G["mute"] if v == 0 else G["vol"])
        total = sum(s["duration"] for s in c.queue)
        self.summary.set_text(f"{len(c.queue)} songs · {fmt_time(total)}" if c.queue else "")
        d = c.duration()
        self.progress.set_range(0, max(1, d))
        self.tlen.set_text(fmt_time(d) if d else "–:––")
        self._tick()

    def _seek_drag(self, scale, scroll, value):
        self.core.seek_to(value)
        return False

    def _tick(self):
        c = self.core
        if not self.get_visible():
            return True
        t = c.elapsed()
        self.progress.set_value(t)
        self.tcur.set_text(fmt_time(t))
        if self.tab == "home":
            self.views["home"].tick(t)
        self.now.tick(t)
        return True

    # ------------------------------------------------------------ thumbnails
    def thumb(self, song):
        key = song.get("yt") or song.get("yt_hint") or \
            (f"album:{song.get('artist')}|{song['album']}" if song.get("album") and not song.get("stream") else None)
        if not key:
            return None
        if key in self.thumbs:
            return self.thumbs[key]
        if key not in self.thumb_wait:
            self.thumb_wait.add(key)
            s = dict(song, yt=song.get("yt") or song.get("yt_hint"))

            def done(path, key=key):
                self.thumbs[key] = path
                self.thumb_wait.discard(key)
                if path and not self.thumb_timer:
                    self.thumb_timer = GLib.timeout_add(350, self._thumbs_ready)
            self.app.thumb_pool.submit(lambda: art.fetch(s, self.core.c)).add_done_callback(
                lambda f: GLib.idle_add(lambda: (done(f.result() if not f.exception() else None), False)[1]))
        return None

    def _thumbs_ready(self):
        self.thumb_timer = None
        self.search.refresh_thumbs()
        for name in ("queue", "youtube"):
            self.views[name].refresh("thumbs")
        self.now.refresh("queue")
        return False

    # ------------------------------------------------------------ visibility
    def show_window(self):
        self.set_visible(True)
        self.present()
        self.root.grab_focus()
        self.core.window_visible = True
        self._tick()

    def hide_window(self):
        self.drop_pending()
        self.set_visible(False)
        self.core.window_visible = False

    # ------------------------------------------------------------ keys
    def _key(self, ctrl, keyval, code, state):
        name = Gdk.keyval_name(keyval) or ""
        ctrl_on = bool(state & Gdk.ModifierType.CONTROL_MASK)
        # Tabs from anywhere (even the search box): Ctrl+Tab / Ctrl+Shift+Tab
        # cycle, Ctrl+0..4 jump.
        if ctrl_on and name in ("Tab", "ISO_Left_Tab"):
            back = name == "ISO_Left_Tab" or bool(state & Gdk.ModifierType.SHIFT_MASK)
            self.step_tab(-1 if back else 1)
            return True
        if ctrl_on and re.fullmatch(r"[0-4]", name):
            self.switch(TABS[int(name)])
            return True
        if self.palette.get_visible():
            return self.palette.key(name, ctrl_on)
        if self.search.get_visible():
            return self.search.key(name, state)
        if self.lpanel.get_visible():
            return self._lp_key(name)
        focus = self.get_focus()
        yt_entry = self.views["youtube"].entry
        # typing into the command line or the YouTube search box
        if self.cmdline.get_visible() and focus is self.cmdline or (focus is not None and focus.is_ancestor(self.cmdline)):
            if name == "Escape":
                self._cmd_close()
                return True
            if name == "BackSpace" and not self.cmdline.get_text():
                self._cmd_close()
                return True
            return False
        if focus is yt_entry or (focus is not None and focus.is_ancestor(yt_entry)):
            if name in ("Escape", "Down", "Tab"):
                self.root.grab_focus()
                self.set_mode("NORMAL")
                return True
            return False
        if self.confirm_cb:
            if keys.is_modifier(name):
                return True
            cb, self.confirm_cb = self.confirm_cb, None
            self.set_mode("NORMAL")
            self.msg.set_text("")
            if name == "y":
                cb()
            else:
                self.toast("Cancelled")
            return True
        if self.help.get_visible():
            return self.help.key(name)
        if keys.is_modifier(name):
            return False
        mods = {m for m, mask in (("ctrl", Gdk.ModifierType.CONTROL_MASK), ("shift", Gdk.ModifierType.SHIFT_MASK),
                                  ("alt", Gdk.ModifierType.ALT_MASK)) if state & mask}
        tok = keys.token(name, mods)
        if tok is None:
            return False
        # the old engine's name for the key: what dispatch() and the views know
        legacy = KEYNAMES.get(name, name)
        if ctrl_on:
            legacy = "C-" + legacy.lower()
        km = self.keymap_now()
        had_count = bool(self.m.count)
        if tok == "<" and not self.m.pending:
            # keys.py reads "<" as the start of <CR>, <C-d>… and would wait:
            # run it at once (with its count)
            n = int(self.m.count or 1)
            self.m.reset()
            self._show_pending()
            self.which.cancel()
            self.run(km.table["<"].action, n, had_count)
            return True
        r = self.m.feed(km, tok)
        self._show_pending()
        if r.kind == "pending":
            if self.m.pending:
                self.which.schedule(km, self.m.pending)
            return True
        self.which.cancel()
        if r.kind == "cancel":
            return True
        if r.kind == "unknown":
            if len(keys.tokens(r.seq)) == 1:
                self.dispatch(legacy, r.count, had_count)   # a key the views know that the keymap doesn't list
            else:
                self.toast(f"{keys.spell(r.seq)} isn't a key here · Space ? shows them")
            return True
        self.run(r.bind.action, r.count, had_count)
        return True

    def keymap_now(self):
        lst = self.views[self.tab].list()
        visual = lst is not None and lst.vstart is not None
        return keys.Keymap(keymap.binds_for(self.tab, visual), keymap.GROUPS)

    def run(self, action, n=1, had_count=False):
        """Run a keymap action (see keymap.py): do:, tab:, call:, moved:."""
        if not isinstance(action, str):
            return
        action, _, note = action.partition("|note:")
        kind, _, arg = action.partition(":")
        if kind == "do":
            self.dispatch(arg, n, had_count)
        elif kind == "tab":
            if arg in ("+1", "-1"):
                self.step_tab(int(arg) * n)
            else:
                self.switch(arg)
        elif kind == "call":
            meth, _, extra = arg.partition(":")
            getattr(self, "k_" + meth)(*([extra] if extra else []))
        elif kind == "moved":
            self.toast(f"That key moved: it's {arg} now")
        if note and note not in self.notes_shown:
            self.notes_shown.add(note)
            self.toast(note)

    def step_tab(self, d):
        i = TABS.index(self.tab) if self.tab in TABS else 0
        self.switch(TABS[(i + d) % len(TABS)])

    # keymap actions (call:<name> runs k_<name>)
    def k_toggle_play(self):
        self.core.toggle()

    def k_palette(self):
        km = self.keymap_now()
        rows = [r for r in keys.palette_rows(km)
                if isinstance(r[2].action, str) and not r[2].action.startswith(("moved:", "call:palette"))]
        self.palette.open(rows)

    def k_keysheet(self):
        extra = [(f"{scope} (its own keys)", [(keys.spell(b.seq), b.desc) for b in bs])
                 for scope, _mode, bs in keymap.PANELS if scope != "leader"]
        self.help.open(self.keymap_now(), keymap.where(self.tab), extra)

    def k_mini(self):
        self.app.show_mini()

    def k_lyrics_pane(self):
        if self.tab == "home":
            self.open_lyrics_panel()
        else:
            self.toggle_lyrics()

    def k_lyrics_panel(self):
        self.open_lyrics_panel()

    def k_lyrics_script(self):
        c = self.core
        c.set_lyrics_script("native" if c.lyrics_script == "latin" else "latin")
        self.toast("Lyrics in Latin letters (Hinglish)" if c.lyrics_script == "latin" else "Lyrics as written (Devanagari)")

    def k_lyrics_nudge(self, d):
        off = self.core.nudge_lyrics(float(d))
        self.toast(f"Lyrics {'earlier' if float(d) < 0 else 'later'}: {off:+.2f} s · kept for this song")

    def k_sleep(self):
        self.sleep("off" if self.sleep_timer else "30m")

    def _song_link(self, s):
        return youtube.watch_url(s["yt"]) if s.get("yt") else s.get("file", "")

    def _copy(self, text, what):
        self.get_clipboard().set(text)
        self.toast(f"Copied {what}")

    def k_copy_song(self):
        s = self.core.current
        if s:
            self._copy(f"{s['title']} · {s.get('artist') or s.get('channel') or ''}".strip(" ·"), "the song")
        else:
            self.toast("Nothing playing")

    def k_copy_link(self):
        s = self.core.current
        if s:
            self._copy(self._song_link(s), "the link" if s.get("yt") else "the file path")
        else:
            self.toast("Nothing playing")

    def k_search(self, scope):
        self.open_search("", int(scope))

    def k_goto_playing(self):
        if self.tab != "queue":
            self.switch("queue")
        self.dispatch("zz")

    def k_open_browser(self):
        s = self.core.current
        if not s or not s.get("yt"):
            self.toast("The playing song isn't from YouTube" if s else "Nothing playing")
            return
        try:
            Gio.AppInfo.launch_default_for_uri(youtube.watch_url(s["yt"]), None)
        except GLib.Error as e:
            self.toast(f"Couldn't open the browser: {e.message}")

    def k_rescan(self):
        try:
            self.core.cmd("update")
        except Exception:   # no MPD: the lists reload anyway
            logging.getLogger("nada.window").debug("rescan: MPD didn't take update", exc_info=True)
        for v in self.views.values():
            v.refresh(None)
        self.toast("Rescanning your music folder")

    def k_clear_queue(self):
        self.confirm("Clear the queue?", lambda: (self.core.clear(), self.toast("Queue cleared · u brings it back")))

    def dispatch(self, k, n=1, had_count=False):
        c = self.core
        view = self.views[self.tab]
        lst = view.list()
        # list motions
        if lst is not None:
            if k == "j":
                lst.move(n)
                return True
            if k == "k":
                lst.move(-n)
                return True
            if k == "gg":
                lst.select(n - 1 if had_count else 0)
                return True
            if k == "G":
                lst.select(n - 1 if had_count else len(lst.items) - 1)
                return True
            if k in ("C-d", "Page_Down"):
                lst.move(lst.page() * n)
                return True
            if k in ("C-u", "Page_Up"):
                lst.move(-lst.page() * n)
                return True
            if k == "V":
                on = lst.visual()
                self.set_mode("VISUAL" if on else "NORMAL")
                return True
            if k == "Escape" and lst.vstart is not None:
                lst.visual(False)
                self.set_mode("NORMAL")
                return True
        elif self.tab == "home" and k in ("j", "k", "gg", "G", "dd", "J", "K", "V", "yy", "p", "P", "A", "C-d", "C-u"):
            self.switch("queue")
            self.toast("The queue · H goes back to the lyrics")
            return self.dispatch(k, n, had_count)
        if view.key(k, n, set()):
            return True
        step = c.conf["seek_step"]
        if k == " ":
            c.toggle()
        elif k == "Return":
            c.toggle()
        elif k == ".":
            c.seek(step * n)
            self.toast(f"Forward {step * n} s · {fmt_time(c.elapsed() + step * n)}")
        elif k == ",":
            c.seek(-step * n)
            self.toast(f"Back {step * n} s · {fmt_time(max(0, c.elapsed() - step * n))}")
        elif k == ">":
            c.next(n)
        elif k == "<":
            c.prev(n)
        elif k in ("=", "+"):
            c.change_volume(c.conf["volume_step"] * n)
        elif k == "-":
            c.change_volume(-c.conf["volume_step"] * n)
        elif k == "m":
            c.mute()
        elif k == "s":
            c.toggle_random()
        elif k == "r":
            c.cycle_repeat()
        elif k == "M":
            c.set_autoplay(not c.autoplay)
        elif k == "L":
            self.k_lyrics_pane()
        elif k == "u":
            c.undo()
        elif k == "C-r":
            c.redo()
        elif k == "D":
            cur = c.current
            if cur:
                c.download(cur)
        elif k == "i":
            cur = c.current
            if cur:
                self.toast(f"{cur['title']} · {cur.get('artist', '')} · " + (youtube.watch_url(cur['yt']) if cur.get('yt') else cur['file']))
        elif k == "/":
            self.open_search()
        elif k == ":":
            self._cmd_open(":")
        elif k == "?":
            self.k_keysheet()
        elif k in ("q", "Escape"):
            self.hide_window()
        elif k == "Tab":
            pass
        else:
            return False
        return True

    # ------------------------------------------------------------ command line
    def _cmd_open(self, prefix):
        self.prefix.set_text(prefix)
        self.msg.set_text("")
        self.cmdline.set_text("")
        self.cmdline.set_visible(True)
        self.msg.set_visible(False)
        self.cmdline.grab_focus()
        self.set_mode("SEARCH" if prefix == "/" else "COMMAND")

    def _cmd_close(self):
        self.prefix.set_text("")
        self.cmdline.set_visible(False)
        self.msg.set_visible(True)
        self.root.grab_focus()
        self.set_mode("NORMAL")

    def _cmd_activate(self, *_):
        text, prefix = self.cmdline.get_text().strip(), self.prefix.get_text()
        self._cmd_close()
        if not text:
            return
        if prefix == "/":
            self.views[self.tab].search(text)
        else:
            self.command(text)

    def command(self, text):
        c = self.core
        cmd, _, arg = text.partition(" ")
        arg = arg.strip()
        if cmd in ("w", "write", "save"):
            c.save_playlist(arg)
        elif cmd in ("e", "edit", "load"):
            if not arg:
                self.switch("playlists")
            else:
                c.load_playlist(arg, "replace")
        elif cmd in ("q", "hide"):
            self.hide_window()
        elif cmd in ("qa", "quit"):
            self.app.quit_all()
        elif cmd in ("yt", "youtube"):
            if arg:
                c.add_url(arg, "play")
            else:
                self.switch("youtube")
        elif cmd == "play":
            hits = c.search_library(arg) if arg else []
            if hits:
                c.add_files([hits[0]["file"]], "play")
            elif arg:
                self.toast(f"Nothing in your library matches “{arg}”: trying YouTube")
                c.add_url(arg, "play")
        elif cmd in ("add",):
            c.add_url(arg, "end")
        elif cmd == "sleep":
            self.sleep(arg)
        elif cmd in ("vol", "volume"):
            try:
                c.set_volume(int(arg.lstrip("+-")) if not arg[:1] in "+-" else c.volume + int(arg))
            except ValueError:
                self.toast(":vol 40  (or +10 / -10)")
        elif cmd == "seek":
            m = re.fullmatch(r"([+-])?(?:(\d+):)?(\d+)", arg)
            if not m:
                self.toast(":seek 1:30  (or +30 / -30)")
            else:
                secs = int(m.group(2) or 0) * 60 + int(m.group(3))
                if m.group(1):
                    c.seek(secs if m.group(1) == "+" else -secs)
                else:
                    c.seek_to(secs)
        elif cmd == "clear":
            c.clear()
            self.toast("Queue cleared · u brings it back")
        elif cmd == "lyrics":
            c.search_lyrics(arg)
        elif cmd == "autoplay":
            c.set_autoplay(arg != "off" if arg else not c.autoplay)
        elif cmd in ("dl", "download"):
            if c.current:
                c.download(c.current)
        elif cmd == "help":
            self.k_keysheet()
        else:
            self.toast(f"Not a command: {cmd} · ? lists them")

    # ------------------------------------------------------------ sleep timer
    def sleep(self, arg):
        if self.sleep_timer:
            GLib.source_remove(self.sleep_timer)
            self.sleep_timer = None
        if arg in ("off", "cancel", "0"):
            self.toast("Sleep timer off")
            return
        m = re.fullmatch(r"(\d+)\s*([hm]?)", arg or "30m")
        if not m:
            self.toast(":sleep 30m  (or 1h, or off)")
            return
        mins = int(m.group(1)) * (60 if m.group(2) == "h" else 1)
        self.sleep_timer = GLib.timeout_add_seconds(mins * 60, self._sleep_fade)
        self.toast(f"Fading out and stopping in {mins} min · :sleep off cancels")

    def _sleep_fade(self):
        c = self.core
        start = c.volume
        steps = [start]

        def step():
            v = steps[0] - max(1, start // 20)
            steps[0] = v
            if v <= 0 or c.state != "play":
                c.cmd("pause", "1")
                if start >= 0:
                    c.set_volume(start)
                return False
            c.set_volume(v)
            return True
        if start > 0:
            GLib.timeout_add(500, step)
        else:
            c.cmd("pause", "1")
        self.sleep_timer = None
        return False
