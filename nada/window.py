"""The player window: tabs, the right pane, controls, the vim mode line,
and the vim key engine (modes, counts, pending operators, registers)."""
import re
import time

from gi.repository import Gdk, GLib, Gtk

from . import art, youtube
from .core import fmt_time
from .views import Downloads, Home, Library, NowPane, Playlists, Queue, YouTube
from .widgets import G, box, hint, keycap, label

# keybind: Nada/everywhere | Ctrl+Tab / Ctrl+Shift+Tab | Switch to the next / previous tab (wraps around)
# keybind: Nada/everywhere | Ctrl+0..5 | Switch to that numbered tab at once (the number shown on it)
# keybind: Nada/everywhere | 0 | Switch to Home (the lyrics)
# keybind: Nada/everywhere | 1 | Switch to the queue
# keybind: Nada/everywhere | 2 | Switch to the library
# keybind: Nada/everywhere | 3 | Switch to YouTube search
# keybind: Nada/everywhere | 4 | Switch to playlists
# keybind: Nada/everywhere | 5 | Switch to downloads
# keybind: Nada/everywhere | j / k | Move down / up a song (counts work: 5j)
# keybind: Nada/everywhere | gg / G | Jump to the top / bottom (12G: to the 12th)
# keybind: Nada/everywhere | Ctrl+d / Ctrl+u | Scroll half a page down / up
# keybind: Nada/everywhere | Space | Toggle play / pause
# keybind: Nada/everywhere | Enter | Play the selected song
# keybind: Nada/everywhere | . / , | Seek forward / back 10 seconds (3. = 30 s)
# keybind: Nada/everywhere | > / < | Play next / previous song
# keybind: Nada/everywhere | = / - | Raise / lower volume
# keybind: Nada/everywhere | m | Toggle mute
# keybind: Nada/everywhere | s | Toggle shuffle
# keybind: Nada/everywhere | r | Cycle repeat (off, all, this song)
# keybind: Nada/everywhere | M | Toggle autoplay (more like this after your songs)
# keybind: Nada/everywhere | V | Select several songs (visual mode)
# keybind: Nada/everywhere | u | Restore the last change (undo)
# keybind: Nada/everywhere | Ctrl+r | Restore an undone change (redo)
# keybind: Nada/everywhere | / | Search (the list; YouTube on 3; your library on 2)
# keybind: Nada/everywhere | n / N | Jump to the next / previous search match
# keybind: Nada/everywhere | : | Run a command (:w name, :sleep 30m, :yt query…)
# keybind: Nada/everywhere | ? | Show all keys
# keybind: Nada/everywhere | z | Switch to the mini player
# keybind: Nada/everywhere | q / Esc | Close the window (the music keeps playing)
# keybind: Nada/queue | dd | Remove the song from the queue (V: the selection)
# keybind: Nada/queue | yy | Copy the song (yank)
# keybind: Nada/queue | p / P | Paste removed or copied songs below / above
# keybind: Nada/queue | J / K | Move the song down / up
# keybind: Nada/queue | A | Move the song to play next
# keybind: Nada/queue | D | Save the YouTube song to your music folder (download)
# keybind: Nada/queue | L | Show the lyrics on the right
# keybind: Nada/queue | zz | Jump to the song that's playing
# keybind: Nada/library | h / l | Move between the columns
# keybind: Nada/library | Tab | Switch between artists, albums, genres and folders
# keybind: Nada/library | a / A | Add to the end of the queue / to play next
# keybind: Nada/youtube | a / A | Add the result to the end of the queue / to play next
# keybind: Nada/youtube | D | Save the result to your music folder (download)
# keybind: Nada/downloads | R | Restart a failed download
# keybind: Nada/downloads | dd | Delete the saved file (asks first)

TABS = ["home", "queue", "library", "youtube", "playlists", "downloads"]
KEYNAMES = {"space": " ", "period": ".", "comma": ",", "greater": ">", "less": "<", "equal": "=", "plus": "+",
            "minus": "-", "slash": "/", "colon": ":", "question": "?", "KP_Enter": "Return", "Up": "k", "Down": "j",
            "KP_Add": "+", "KP_Subtract": "-", "BackSpace": "BackSpace", "bracketleft": "[", "bracketright": "]"}
HELP = [
    ("Move", [("j k", "down / up (5j counts)"), ("gg G", "top / bottom"), ("Ctrl+d Ctrl+u", "half a page"),
              ("h l", "columns (library)"), ("zz", "the playing song"), ("0", "home: lyrics"), ("1–5", "queue, library, YouTube…")]),
    ("Play", [("Enter", "play the selected song"), ("space", "play / pause"), (". ,", "forward / back 10 s"),
              ("> <", "next / previous song"), ("= - m", "volume, mute"), ("s r", "shuffle, repeat"), ("M", "autoplay on/off")]),
    ("Queue", [("dd", "remove"), ("J K", "move down / up"), ("yy p P", "copy, paste below / above"), ("A", "play next"),
               ("V", "select several"), ("u Ctrl+r", "undo, redo"), ("D", "download (YouTube)")]),
    ("More", [("L", "lyrics (queue)"), ("/ n N", "search, next, previous"), (":", "commands"), ("i", "song info"),
              ("z", "mini player"), ("q Esc", "close (keeps playing)"), (":w :e", "save / load a playlist")]),
]
COMMANDS = ":w <name> save the queue · :e <name> load a playlist · :yt <search> · :play <search> · :sleep 30m · :vol 40 · " \
           ":seek 1:30 · :lyrics <search> · :autoplay on/off · :clear · :dl · :q · :qa"


class Window(Gtk.ApplicationWindow):
    def __init__(self, app, core):
        super().__init__(application=app, title="nāda")
        self.app, self.core = app, core
        self.add_css_class("nada")
        self.set_default_size(1180, 720)
        self.register = []
        self.count, self.pending, self.mode = "", "", "NORMAL"
        self.confirm_cb = None
        self.tab = "home"
        self.thumbs, self.thumb_wait = {}, set()
        self.thumb_timer = None
        self.toast_timer = None
        self.digit_timer = None
        self.z_timer = None
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
        for i, cls in enumerate([Home, Queue, Library, YouTube, Playlists, Downloads]):
            v = cls(self)
            self.views[v.name] = v
            b = Gtk.Button()
            b.add_css_class("tab")
            b.set_child(box(keycap(str(i)), label(v.title, ellipsize=False), spacing=7))
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
        self.help = self._help()
        self.help.set_visible(False)
        overlay.add_overlay(self.help)

        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._key)
        self.add_controller(keys)
        self.connect("close-request", lambda *_: (self.hide_window(), True)[1])
        self.connect("notify::visible", lambda *_: setattr(self.core, "window_visible", self.get_visible()))

        core.listen(self._core_event)
        for v in self.views.values():
            v.refresh(None)
        self.now.refresh(None)
        self._update_controls()
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
        c = self.core
        step = lambda: c.conf["seek_step"]
        self.pp = self._btn(G["play"], "Play / pause  (space)", c.toggle, big=True)
        ctl = box(self._btn(G["prev"], "Previous song  (<)", c.prev),
                  self._btn(G["back"], "Back 10 seconds  (,)", lambda: c.seek(-step())),
                  self.pp,
                  self._btn(G["fwd"], "Forward 10 seconds  (.)", lambda: c.seek(step())),
                  self._btn(G["next"], "Next song  (>)", c.next), spacing=2)
        self.tcur = label("0:00", "time", ellipsize=False)
        self.tlen = label("0:00", "time", ellipsize=False)
        self.progress = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self.progress.set_draw_value(False)
        self.progress.set_hexpand(True)
        self.progress.add_css_class("progress")
        self.progress.set_focusable(False)
        self.progress.connect("change-value", self._seek_drag)
        self.shuf = self._btn(G["shuffle"], "Shuffle  (s)", c.toggle_random)
        self.rep = self._btn(G["repeat"], "Repeat: off, all, this song  (r)", c.cycle_repeat)
        self.volglyph = self._btn(G["vol"], "Mute  (m)", c.mute)
        self.vol = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol.set_draw_value(False)
        self.vol.set_size_request(80, -1)
        self.vol.add_css_class("volume")
        self.vol.set_focusable(False)
        self.vol.connect("change-value", lambda _s, _t, v: (c.set_volume(v), False)[1])
        self.volv = label("", "time", ellipsize=False)
        self.volv.set_size_request(26, -1)
        side = box(self.shuf, self.rep, self.volglyph, self.vol, self.volv, spacing=4)
        return box(ctl, box(self.tcur, self.progress, self.tlen, spacing=10, hexpand=True, margin_start=10, margin_end=10),
                   side, cls="bar", spacing=8)

    def _help(self):
        grid = Gtk.Grid(column_spacing=34, row_spacing=4, column_homogeneous=True)
        for col, (title, rows) in enumerate(HELP):
            grid.attach(label(title.upper(), "h"), col, 0, 1, 1)
            for r, (k, d) in enumerate(rows, 1):
                b = box(spacing=8)
                b.append(box(*[keycap(x) for x in k.split()], spacing=3, halign=Gtk.Align.END))
                b.append(label(d, "d"))
                grid.attach(b, col, r, 1, 1)
        cmds = label(COMMANDS, "d", wrap=True, margin_top=14)
        return box(grid, cmds, label("? or Esc closes this", "dim", margin_top=10), vertical=True, cls="help",
                   valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)

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
        self.set_mode("NORMAL")
        self._hints()
        if self.cmdline.get_visible():
            self._cmd_close()

    def toggle_lyrics(self):
        if self.tab == "home":
            self.toast("Home already shows the lyrics · 1 for the queue")
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
        for m in ("visual", "search", "command", "confirm"):
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
        self.msg.set_text(f"{self.count}{self.pending}")

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
        self.msg.set_text(f"{question}  y / n")

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
        self.set_visible(False)
        self.core.window_visible = False

    # ------------------------------------------------------------ keys
    def _key(self, ctrl, keyval, code, state):
        name = Gdk.keyval_name(keyval) or ""
        ctrl_on = bool(state & Gdk.ModifierType.CONTROL_MASK)
        # Tabs, the same keys as Vyom's panels, from anywhere (even the
        # search box): Ctrl+Tab / Ctrl+Shift+Tab cycle, Ctrl+0..5 jump at
        # once (a bare digit waits a moment, in case it's a count like 5j).
        if ctrl_on and name in ("Tab", "ISO_Left_Tab"):
            back = name == "ISO_Left_Tab" or bool(state & Gdk.ModifierType.SHIFT_MASK)
            i = TABS.index(self.tab) if self.tab in TABS else 0
            self.switch(TABS[(i + (-1 if back else 1)) % len(TABS)])
            return True
        if ctrl_on and re.fullmatch(r"[0-5]", name):
            self.switch(TABS[int(name)])
            return True
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
            if name == "Escape":
                self.root.grab_focus()
                self.set_mode("NORMAL")
                return True
            if name in ("Down", "Tab"):
                self.root.grab_focus()
                self.set_mode("NORMAL")
                return True
            return False
        if self.confirm_cb:
            cb, self.confirm_cb = self.confirm_cb, None
            self.set_mode("NORMAL")
            self.msg.set_text("")
            if name in ("y", "Y", "Return"):
                cb()
            else:
                self.toast("Cancelled")
            return True
        if self.help.get_visible():
            if name in ("question", "Escape", "q"):
                self.help.set_visible(False)
            return True
        if name in ("Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Super_L", "Super_R", "ISO_Level3_Shift"):
            return False
        k = KEYNAMES.get(name, name)
        if ctrl_on:
            k = "C-" + k.lower()
        # counts (a lone 0 or 1-5 with nothing after it switches tabs)
        if re.fullmatch(r"[0-9]", k) and not self.pending:
            if k == "0" and not self.count:
                self.switch("home")
                return True
            self.count += k
            self._show_pending()
            if self.digit_timer:
                GLib.source_remove(self.digit_timer)
            if re.fullmatch(r"[1-5]", self.count):
                c = self.count
                self.digit_timer = GLib.timeout_add(650, self._digit_tab, c)
            return True
        if self.digit_timer:
            GLib.source_remove(self.digit_timer)
            self.digit_timer = None
        n = int(self.count or "1")
        had_count = bool(self.count)
        self.count = ""
        if self.pending:
            combo, self.pending = self.pending + k, ""
            if self.z_timer:
                GLib.source_remove(self.z_timer)
                self.z_timer = None
            self._show_pending()
            if combo in ("gg", "dd", "dG", "yy", "zz"):
                self.dispatch(combo, n, had_count)
            return True
        view = self.views[self.tab]
        lst = view.list()
        visual = lst is not None and lst.vstart is not None
        if k in ("g", "d", "y") and not (visual and k in ("d", "y")):
            if k != "g" and self.tab not in ("queue", "playlists", "downloads"):
                return self.dispatch(k, n, had_count) or True
            self.pending = k
            self.count = str(n) if had_count else ""
            self._show_pending()
            return True
        if k == "z":
            self.pending = "z"
            self._show_pending()
            self.z_timer = GLib.timeout_add(450, self._z_alone)
            return True
        self.dispatch(k, n, had_count)
        return True

    def _digit_tab(self, c):
        self.digit_timer = None
        if self.count == c:
            self.count = ""
            self._show_pending()
            self.switch(TABS[int(c)])
        return False

    def _z_alone(self):
        self.z_timer = None
        if self.pending == "z":
            self.pending = ""
            self._show_pending()
            self.app.show_mini()
        return False

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
            self.toast("The queue (1) · 0 goes back to the lyrics")
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
            self.toggle_lyrics()
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
            if self.tab == "youtube":
                self.views["youtube"].focus_entry()
            else:
                self._cmd_open("/")
        elif k == ":":
            self._cmd_open(":")
        elif k == "?":
            self.help.set_visible(True)
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
            self.help.set_visible(True)
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
