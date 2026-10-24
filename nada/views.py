"""The six tabs (Home, Queue, Library, YouTube, Playlists, Downloads) and
the right-hand pane. Keys common to every list (j k gg G Ctrl+d/u V) are
handled by the window; each view handles its own."""
import os
import time

from gi.repository import Gdk, GLib, GObject, Gtk

from . import youtube
from .core import fmt_time
from .widgets import G, LyricsView, RowList, box, esc, hint, label, picture, tile


def song_meta(song, show_album=True):
    """"Artist · 536.7M views · 14 years ago" (YouTube) or "Artist · Album" (files)."""
    parts = [song.get("artist") or song.get("channel") or ""]
    if song.get("views"):
        parts.append(youtube.views(song["views"]))
    if song.get("uploaded"):
        parts.append(youtube.ago(song["uploaded"]))
    elif show_album and song.get("album"):
        parts.append(song["album"])
    return " · ".join(p for p in parts if p)


def badge(kind, pct=None):
    text = {"local": "local", "yt": "YT", "dl": f"{G['dl']} {int(pct or 0)}%", "failed": "failed"}[kind]
    return label(text, f"badge {kind}", ellipsize=False, valign=Gtk.Align.CENTER)


def section(text, right=None):
    b = box(label(text.upper(), hexpand=True), cls="sect", spacing=8)
    if right is not None:
        b.append(right)
    return b


class View:
    name = title = glyph = ""
    hints = []

    def __init__(self, win):
        self.win, self.core = win, win.core
        self.widget = None

    def list(self):
        return None

    def refresh(self, event=None):
        pass

    def key(self, k, n, mods):
        return False

    def search(self, q):
        self.win.toast("Nothing to search here")

    def shown(self):
        pass

    def thumb_or_tile(self, song, size=38):
        key = song.get("yt") or song.get("yt_hint") or (song.get("album") and f"{song.get('artist')}|{song['album']}") or song.get("file", "")
        path = self.win.thumb(song)
        w = picture(path, size, "tile") if path else None
        return w or tile(key, song.get("title"), size)


# ===================================================================== home
class Home(View):
    """Now playing: the lyrics, big, the current line lit. Above them, where
    they came from and how they're shown; L opens the lyrics panel."""
    name, title, glyph = "home", "Now", G["home"]
    hints = [("space", "play"), (", .", "±10 s"), ("L", "lyrics"), ("/", "search")]

    def __init__(self, win):
        super().__init__(win)
        self.lyr = LyricsView(self.core.seek_to, big=True)
        self.chips = box(spacing=8, cls="lyrics-head")
        foot = box(hint("L", "pick lyrics, script, timing"), hint(", .", "±10 s"), label("click a line to jump there", "dim"),
                   spacing=16, cls="lyrics-foot")
        self.widget = box(self.chips, self.lyr, foot, vertical=True, hexpand=True)

    def _chips(self, L):
        child = self.chips.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.chips.remove(child)
            child = nxt
        c = self.core
        if L.get("loading"):
            self.chips.append(label("looking for lyrics…", "chip", ellipsize=False))
        elif L.get("error"):
            self.chips.append(label("● can't reach the lyrics sources", "chip warn", ellipsize=False))
        elif L.get("lines"):
            kind = "synced" if L.get("synced") else "plain"
            self.chips.append(label(f"● {kind} · {L.get('source') or '?'}", "chip ok" if L.get("synced") else "chip",
                                    ellipsize=False))
            if L.get("devanagari"):
                self.chips.append(label("Hinglish" if c.lyrics_script == "latin" else "हिन्दी", "chip", ellipsize=False))
            if L.get("offset"):
                self.chips.append(label(f"timing {L['offset']:+.2f} s", "chip", ellipsize=False))
            if L.get("manual"):
                self.chips.append(label("your pick", "chip act", ellipsize=False))
        self.chips.append(Gtk.Box(hexpand=True))
        self.chips.append(label("L  lyrics", "chip act", ellipsize=False))

    def refresh(self, event=None):
        if event in (None, "lyrics", "song", "connection"):
            c = self.core
            L = c.lyrics
            cur = c.current
            if not c.connected:
                self.lyr.set(None, message=f"{c.error or 'Connecting to MPD…'}\n\nStart it: systemctl --user start mpd")
            elif not cur:
                self.lyr.set(None, message="Nothing playing.\n\n/ searches your library and YouTube")
            elif L.get("loading"):
                self.lyr.set(None, message="Looking for the lyrics…\nYouTube Music, LRCLIB, NetEase")
            elif L.get("error") == "unreachable":
                self.lyr.set(None, message="Couldn't reach the lyrics sources (no network, or they're busy).\n"
                                           "Trying again in 30 s · L to look by hand")
            elif not L.get("lines"):
                self.lyr.set(None, message="No lyrics for this song on YouTube Music, LRCLIB or NetEase.\n"
                                           "L to look by hand · :lyrics <words> to search with your own")
            else:
                self.lyr.set(L, key=f"{L.get('for')}|{c.lyrics_script}|{L.get('offset')}|{L.get('source')}")
            self._chips(L)

    def tick(self, t):
        self.lyr.update(t)


# ===================================================================== queue
class Queue(View):
    name, title, glyph = "queue", "Queue", G["queue"]
    hints = [("Enter", "play"), ("dd", "remove"), ("J K", "move"), ("L", "lyrics"), ("D", "download")]

    def __init__(self, win):
        super().__init__(win)
        self.rows = RowList(on_activate=lambda s: self.core.play_pos(s["pos"]))
        self.widget = self.rows
        self.matches, self.mi = [], 0

    def list(self):
        return self.rows

    def row(self, s, playing, past):
        c = self.core
        kind = c.kind(s)
        job = c.job_for(s["yt"]) if s.get("yt") else None
        grip = label("⠿", "grip", ellipsize=False)
        no = label(G["pause"] if playing and c.state == "pause" else ("▶" if playing else str(s["pos"] + 1)), "no",
                   xalign=1, ellipsize=False)
        text = box(label(s["title"], "title"), label(song_meta(s), "sub"), vertical=True, hexpand=True,
                   valign=Gtk.Align.CENTER)
        x = Gtk.Button(label="×", valign=Gtk.Align.CENTER, tooltip_text="Remove from the queue (dd)")
        x.add_css_class("x")
        x.connect("clicked", lambda *_: c.delete([s["pos"]]))
        w = box(grip, no, self.thumb_or_tile(s), text, badge(kind, job["pct"] if job else None),
                label(fmt_time(s["duration"]) if s["duration"] else "", "dur", xalign=1, ellipsize=False), x, spacing=10)
        if playing:
            w.add_css_class("playing")
        if past:
            w.add_css_class("past")
        # drag to reorder
        src = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        src.connect("prepare", lambda *_: Gdk.ContentProvider.new_for_value(GObject.Value(GObject.TYPE_INT, s["pos"])))
        w.add_controller(src)
        dst = Gtk.DropTarget.new(GObject.TYPE_INT, Gdk.DragAction.MOVE)
        dst.connect("enter", lambda *_: (w.add_css_class("drop"), Gdk.DragAction.MOVE)[1])
        dst.connect("leave", lambda *_: w.remove_css_class("drop"))
        dst.connect("drop", lambda _t, frm, *_: self._dropped(frm, s["pos"]))
        w.add_controller(dst)
        return w

    def _dropped(self, frm, to):
        if self.core.move(frm, to):
            self.win.toast("That song is in your queue now: autoplay won't replace it")
        self.rows.sel = to
        return True

    def refresh(self, event=None):
        if event not in (None, "queue", "player", "song", "downloads", "options", "thumbs"):
            return
        c = self.core
        p = c.cur_pos
        rows = []
        q = c.queue
        if not q:
            rows = []
        for s in q:
            i = s["pos"]
            if i == 0 and p > 0:
                rows.append(("header", section("Played", label(str(p), ellipsize=False))))
            if i == 0 and p < 0:
                rows.append(("header", section("Queue")))
            if i == p:
                rows.append(("header", section("Now playing")))
            if p >= 0 and i == p + 1 and not s["auto"]:
                mine = sum(1 for x in q[p + 1:] if not x["auto"])
                rows.append(("header", section("Next in queue · added by you", label(str(mine), ellipsize=False))))
            if s["auto"] and i > p and (i == p + 1 or not q[i - 1]["auto"]):
                seed = c.current["title"] if c.current else ""
                chip = label(f"{G['radio']} on · M turns it off", "sect-chip", ellipsize=False)
                rows.append(("header", section(f"Autoplay · more like “{seed[:40]}”", chip)))
            rows.append(("item", s, self.row(s, i == p, p >= 0 and i < p)))
        if q and not c.autoplay:
            rows.append(("header", section("Autoplay is off · stops after your songs",
                                           label("M turns it on", "sect-chip off", ellipsize=False))))
        empty = label("The queue is empty.\n\n3 searches YouTube · 2 browses your library\n"
                      ":yt <search> plays the top YouTube result", "empty", xalign=0.5, wrap=True,
                      justify=Gtk.Justification.CENTER)
        self.rows.set_rows(rows, empty=empty)

    def shown(self):
        if self.core.cur_pos >= 0 and not getattr(self, "_placed", False):
            self._placed = True
            self.rows.select(self.core.cur_pos)

    def selected_songs(self):
        return [self.rows.items[i] for i in self.rows.range() if i < len(self.rows.items)]

    def key(self, k, n, mods):
        c, w = self.core, self.win
        s = self.rows.selected()
        if k == "Return":
            if s:
                c.play_pos(s["pos"])
            return True
        if k in ("dd", "x", "Delete", "d") and (k != "d" or self.rows.vstart is not None):
            songs = self.selected_songs() if self.rows.vstart is not None else self.rows.items[self.rows.sel:self.rows.sel + n]
            if songs:
                w.register = c.delete([x["pos"] for x in songs])
                w.toast(f"Removed {len(songs)} song{'s' if len(songs) > 1 else ''} · u undo · p put back")
            self.rows.visual(False)
            w.set_mode("NORMAL")
            return True
        if k == "dG":
            songs = self.rows.items[self.rows.sel:]
            w.register = c.delete([x["pos"] for x in songs])
            w.toast(f"Removed {len(songs)} songs · u undo")
            return True
        if k in ("yy", "y") and (k != "y" or self.rows.vstart is not None):
            songs = self.selected_songs() if self.rows.vstart is not None else self.rows.items[self.rows.sel:self.rows.sel + n]
            w.register = [c._entry(x) for x in songs]
            w.toast(f"Yanked {len(songs)} · p puts below, P above")
            self.rows.visual(False)
            w.set_mode("NORMAL")
            return True
        if k in ("p", "P"):
            if not w.register:
                w.toast("Nothing yanked or removed yet")
                return True
            at = (s["pos"] + 1 if k == "p" else s["pos"]) if s else len(c.queue)
            c.put([dict(e, meta=dict(e.get("meta") or {})) for e in w.register], at)
            self.rows.sel = at
            w.toast(f"Put {len(w.register)} {'below' if k == 'p' else 'above'}")
            return True
        if k in ("J", "K") and s:
            to = s["pos"] + (n if k == "J" else -n)
            to = max(0, min(len(c.queue) - 1, to))
            if c.move(s["pos"], to):
                w.toast("That song is in your queue now: autoplay won't replace it")
            self.rows.sel = to
            return True
        if k == "A" and s and s["pos"] != c.cur_pos:
            to = c.cur_pos + (1 if s["pos"] > c.cur_pos else 0)
            c.move(s["pos"], max(0, to))
            self.rows.sel = max(0, to)
            w.toast(f"{s['title'][:40]} plays next")
            return True
        if k == "D":
            songs = self.selected_songs() if self.rows.vstart is not None else ([s] if s else [])
            yts = [x for x in songs if x.get("yt") and x.get("stream")]
            if not yts:
                w.toast("Only YouTube songs need downloading: these are files already")
            for x in yts:
                c.download(x)
            self.rows.visual(False)
            w.set_mode("NORMAL")
            return True
        if k == "zz":
            if c.cur_pos >= 0:
                self.rows.select(c.cur_pos)
            return True
        if k == "i" and s:
            w.toast(f"{s['title']} · {song_meta(s)} · " + (youtube.watch_url(s['yt']) if s.get('yt') else s['file']))
            return True
        if k in ("n", "N") and self.matches:
            self.mi = (self.mi + (1 if k == "n" else -1)) % len(self.matches)
            self.rows.select(self.matches[self.mi])
            return True
        if k == "a":
            w.toast("Already in the queue · A plays it next")
            return True
        return False

    def search(self, q):
        q = q.lower()
        self.matches = [i for i, s in enumerate(self.rows.items)
                        if q in f"{s['title']} {s['artist']} {s.get('album', '')}".lower()]
        self.mi = 0
        if self.matches:
            nxt = next((m for m in self.matches if m >= self.rows.sel), self.matches[0])
            self.mi = self.matches.index(nxt)
            self.rows.select(nxt)
            self.win.toast(f"{len(self.matches)} match{'es' if len(self.matches) > 1 else ''} · n / N to step")
        else:
            self.win.toast(f"No match for “{q}”")


# ===================================================================== library
class Library(View):
    name, title, glyph = "library", "Library", G["lib"]
    hints = [("h l", "columns"), ("Enter", "play"), ("a", "add"), ("Tab", "artists/albums/genres/folders"), ("/", "search")]
    MODES = ["Artists", "Albums", "Genres", "Folders"]

    def __init__(self, win):
        super().__init__(win)
        self.mode = 0
        self.focus = 0
        self.cols = [RowList(on_activate=lambda d, i=i: self._enter(i), on_select=lambda d, i=i: self._selected(i))
                     for i in range(3)]
        self.heads = [label("", "sect") for _ in range(3)]
        self.frames = []
        for i, (h, c) in enumerate(zip(self.heads, self.cols, strict=True)):
            f = box(h, c, vertical=True, hexpand=True, cls="col")
            if i == 2:
                f.remove_css_class("col")
            self.frames.append(f)
        self.frames[0].set_size_request(220, -1)
        self.frames[1].set_size_request(240, -1)
        self.widget = box(*self.frames)
        self.loaded = False
        self.query = None
        self.pending = None

    def list(self):
        return self.cols[self.focus]

    def shown(self):
        if not self.loaded:
            self.reload()

    def refresh(self, event=None):
        if event == "database" and self.loaded:
            self.reload()

    def _focus(self, i):
        self.focus = max(0, min(2, i))
        for j, f in enumerate(self.frames):
            (f.add_css_class if j == self.focus else f.remove_css_class)("focus")

    def _fill(self, i, items, title):
        self.heads[i].set_text(title.upper())
        rows = [("item", d, self._row(d)) for d in items]
        empty = label("Nothing here" if self.core.connected else "MPD isn't connected", "empty", xalign=0.5)
        self.cols[i].sel = 0
        self.cols[i].set_rows(rows, keep=False, empty=empty)

    def _row(self, d):
        if d["kind"] == "song":
            s = d["song"]
            dur = fmt_time(float(s.get("duration") or s.get("Time") or 0))
            t = box(label(s.get("Title") or os.path.basename(s["file"]), "title"),
                    label(s.get("Artist", ""), "sub"), vertical=True, hexpand=True)
            return box(label(s.get("Track", "").split("/")[0], "no", xalign=1, ellipsize=False), t,
                       label(dur, "dur", xalign=1, ellipsize=False), spacing=10)
        glyph = {"artist": G["artist"], "album": G["album"], "genre": G["note"], "dir": G["folder"]}.get(d["kind"], G["note"])
        return box(label(glyph, "glyph dim", ellipsize=False), label(d["name"], "title", hexpand=True), spacing=10)

    def reload(self):
        self.loaded = True
        self.query = None
        c = self.core
        mode = self.MODES[self.mode]
        self._focus(0)

        def work():
            if mode == "Artists":
                return [{"kind": "artist", "name": a} for a in c.lib_list("artists")]
            if mode == "Albums":
                return [{"kind": "album", "name": a} for a in c.lib_list("albums", "") or
                        [v for v in c.c.values("list", "album") if v]]
            if mode == "Genres":
                return [{"kind": "genre", "name": g} for g in c.lib_list("genres")]
            return self._dir("")

        def then(items):
            self._fill(0, items, f"{mode} · {len(items)}")
            self._fill(1, [], "")
            self._fill(2, [], "")
            self._selected(0)
        self.core.bg(work, then)

    def _dir(self, path):
        out = []
        for it in self.core.lib_list("folder", path):
            if "directory" in it:
                out.append({"kind": "dir", "name": os.path.basename(it["directory"]), "path": it["directory"]})
            elif "file" in it:
                out.append({"kind": "song", "song": it})
        return out

    def _selected(self, i):
        """Selection moved in column i: fill the next column (debounced)."""
        if i >= 2 or self.query is not None:
            return
        if self.pending:
            GLib.source_remove(self.pending)
        self.pending = GLib.timeout_add(90, self._load_next, i)

    def _load_next(self, i):
        self.pending = None
        d = self.cols[i].selected()
        c = self.core
        if not d:
            return False

        def work():
            if d["kind"] == "artist":
                albums = c.lib_list("albums", d["name"])
                if albums:
                    return [{"kind": "album", "name": a, "artist": d["name"]} for a in albums], "Albums"
                songs = c.c.items("find", "albumartist", d["name"]) or c.c.items("find", "artist", d["name"])
                return [{"kind": "song", "song": s} for s in songs], "Songs"
            if d["kind"] == "album":
                return [{"kind": "song", "song": s} for s in c.lib_list("songs", (d.get("artist", ""), d["name"]))], d["name"]
            if d["kind"] == "genre":
                return [{"kind": "album", "name": a, "artist": ""} for a in c.lib_list("genre_albums", d["name"])], "Albums"
            if d["kind"] == "dir":
                return self._dir(d["path"]), d["name"]
            return None, None

        def then(r):
            items, title = r
            if items is None:
                return
            self._fill(i + 1, items, f"{title} · {len(items)}")
            if i + 1 < 2:
                self._selected(i + 1)
        c.bg(work, then)
        return False

    def _uris(self, d):
        c = self.core
        if d["kind"] == "song":
            return [d["song"]["file"]]
        if d["kind"] == "album":
            return [s["file"] for s in c.lib_list("songs", (d.get("artist", ""), d["name"]))]
        if d["kind"] == "artist":
            return [s["file"] for s in c.c.items("find", "albumartist", d["name"])] or \
                   [s["file"] for s in c.c.items("find", "artist", d["name"])]
        if d["kind"] == "genre":
            return [s["file"] for s in c.c.items("find", "genre", d["name"])]
        if d["kind"] == "dir":
            return [v for k, v in c.c.pairs("listall", d["path"]) if k == "file"]
        return []

    def _enter(self, i):
        self._add(i, "play")

    def _add(self, i, where):
        col = self.cols[i]
        items = [col.items[j] for j in col.range()]
        uris = []
        for d in items:
            uris += self._uris(d)
        col.visual(False)
        self.win.set_mode("NORMAL")
        if not uris:
            self.win.toast("No songs there")
            return
        self.core.add_files(uris, where)
        if where != "play":
            self.win.toast(f"{'Plays next' if where == 'next' else 'Added'}: {len(uris)} song{'s' if len(uris) > 1 else ''}")

    def key(self, k, n, mods):
        if k == "l" or k == "Right":
            if self.focus < 2 and self.cols[self.focus + 1].items:
                self._focus(self.focus + 1)
            return True
        if k == "h" or k == "Left":
            self._focus(self.focus - 1)
            return True
        if k == "Tab":
            self.mode = (self.mode + 1) % len(self.MODES)
            self.reload()
            self.win.toast(f"Library by {self.MODES[self.mode].lower()}")
            return True
        if k == "Return":
            self._add(self.focus, "play")
            return True
        if k == "a":
            self._add(self.focus, "end")
            return True
        if k == "A":
            self._add(self.focus, "next")
            return True
        if k == "Escape" and self.query is not None:
            self.reload()
            return True
        return False

    def search(self, q):
        self.query = q

        def then(songs):
            self._fill(2, [{"kind": "song", "song": s} for s in songs], f"Search “{q}” · {len(songs)}")
            self._focus(2)
            if not songs:
                self.win.toast(f"Nothing in your library matches “{q}” · 3 then / searches YouTube")
            else:
                self.win.toast("Esc goes back to browsing")
        self.core.bg(lambda: self.core.search_library(q), then)


# ===================================================================== youtube
class YouTube(View):
    name, title, glyph = "youtube", "YouTube", G["yt"]
    hints = [("/", "search"), ("Enter", "play"), ("a", "add"), ("A", "play next"), ("D", "download")]

    def __init__(self, win):
        super().__init__(win)
        self.entry = Gtk.Text(hexpand=True, placeholder_text="Search YouTube…   (/ to type, Enter to search, Esc back to the results)")
        self.entry.connect("activate", lambda *_: self._go())
        self.spin = label("", "dim", ellipsize=False)
        sb = box(label(G["search"] + "  ", "glyph dim", ellipsize=False), self.entry, self.spin, cls="searchbox")
        self.rows = RowList(on_activate=lambda e: self.core.add_yt([e], "play"))
        self.widget = box(sb, self.rows, vertical=True, hexpand=True)
        self.results = []
        self._fill()

    def list(self):
        return self.rows

    def shown(self):
        if not self.results:
            GLib.idle_add(lambda: (self.focus_entry(), False)[1])

    def focus_entry(self):
        self.entry.grab_focus()
        self.win.set_mode("SEARCH")

    def _go(self):
        q = self.entry.get_text().strip()
        self.win.root.grab_focus()
        self.win.set_mode("NORMAL")
        if q:
            self.search(q)

    def search(self, q):
        self.entry.set_text(q)
        self.spin.set_text("searching…")

        def then(results):
            self.spin.set_text(f"{len(results)} results")
            self.results = results
            self._fill()
            self.rows.select(0)

        def fail(e):
            self.spin.set_text("")
            self.win.toast(str(e))
        self.core.bg(lambda: youtube.search(q, 25), then, fail)

    def _fill(self):
        rows = []
        for e in self.results:
            text = box(label(e["title"], "title"), label(song_meta(e), "sub"), vertical=True, hexpand=True,
                       valign=Gtk.Align.CENTER)
            queued = e["yt"] in {s.get("yt") for s in self.core.queue}
            w = box(self.thumb_or_tile(e, 46), text,
                    label("in queue", "badge local", ellipsize=False, valign=Gtk.Align.CENTER) if queued else None,
                    label(fmt_time(e["duration"]), "dur", xalign=1, ellipsize=False), spacing=12)
            rows.append(("item", e, w))
        empty = label(f"{G['yt']}\n\nSearch YouTube: press / and type.\nEnter plays it (and what comes after it),\n"
                      "a adds it to the queue, D downloads it.", "empty", xalign=0.5, wrap=True,
                      justify=Gtk.Justification.CENTER)
        self.rows.set_rows(rows, empty=empty)

    def refresh(self, event=None):
        if event in ("thumbs", "queue") and self.results:
            self._fill()

    def key(self, k, n, mods):
        e = self.rows.selected()
        sel = [self.rows.items[i] for i in self.rows.range()] if self.rows.items else []
        if k == "Return" and e:
            self.core.add_yt([e], "play")
            return True
        if k in ("a", "A") and sel:
            self.core.add_yt(sel, "end" if k == "a" else "next")
            self.rows.visual(False)
            self.win.set_mode("NORMAL")
            return True
        if k == "D" and sel:
            for x in sel:
                self.core.download(x)
            self.rows.visual(False)
            self.win.set_mode("NORMAL")
            return True
        if k == "i" and e:
            self.win.toast(f"{e['raw_title'][:90]} · {song_meta(e)}")
            return True
        return False


# ===================================================================== playlists
class Playlists(View):
    name, title, glyph = "playlists", "Playlists", G["list"]
    hints = [("Enter", "play"), ("a", "add"), ("dd", "delete"), (":w name", "save the queue"), (":e name", "load")]

    def __init__(self, win):
        super().__init__(win)
        self.focus = 0
        self.left = RowList(on_activate=lambda n: self.core.load_playlist(n, "play"), on_select=lambda n: self._show(n))
        self.right = RowList()
        self.lhead, self.rhead = label("PLAYLISTS", "sect"), label("", "sect")
        lf = box(self.lhead, self.left, vertical=True, cls="col")
        lf.set_size_request(260, -1)
        self.widget = box(lf, box(self.rhead, self.right, vertical=True, hexpand=True))

    def list(self):
        return self.left if self.focus == 0 else self.right

    def shown(self):
        self.refresh("playlists")

    def refresh(self, event=None):
        if event not in (None, "playlists", "connection"):
            return
        names = self.core.playlists()
        rows = [("item", n, box(label(G["list"], "glyph dim", ellipsize=False), label(n, "title", hexpand=True), spacing=10))
                for n in names]
        self.lhead.set_text(f"PLAYLISTS · {len(names)}")
        self.left.set_rows(rows, empty=label("No playlists yet.\n\n:w <name> saves the queue as one.", "empty",
                                             xalign=0.5, wrap=True, justify=Gtk.Justification.CENTER))
        self._show(self.left.selected())

    def _show(self, name):
        if not name:
            self.right.set_rows([])
            self.rhead.set_text("")
            return
        songs = self.core.playlist_songs(name)
        rows = []
        for i, s in enumerate(songs):
            vid = youtube.video_id(s["file"])
            known = self.core.yt_titles.get(vid) if vid else None
            title = s.get("Title") or (known[0] if known else f"YouTube · {vid}" if vid else os.path.basename(s["file"]))
            artist = s.get("Artist") or (known[1] if known else "")
            t = box(label(title, "title"), label(artist, "sub"), vertical=True, hexpand=True)
            rows.append(("item", s, box(label(str(i + 1), "no", xalign=1, ellipsize=False), t,
                                        badge("yt" if vid else "local"), spacing=10)))
        self.rhead.set_text(f"{name.upper()} · {len(songs)} SONGS")
        self.right.set_rows(rows, keep=False)

    def key(self, k, n, mods):
        name = self.left.selected()
        if k in ("l", "Right") and self.right.items:
            self.focus = 1
            return True
        if k in ("h", "Left"):
            self.focus = 0
            return True
        if not name:
            return False
        if k == "Return":
            self.core.load_playlist(name, "play")
            return True
        if k == "a":
            self.core.load_playlist(name, "end")
            return True
        if k == "A":
            self.core.load_playlist(name, "next")
            return True
        if k == "dd" and self.focus == 0:
            self.win.confirm(f"Delete the playlist “{name}”?", lambda: self.core.delete_playlist(name))
            return True
        if k == "D":
            n_yt = sum(1 for s in self.core.playlist_songs(name) if youtube.video_id(s["file"]))
            for s in self.core.playlist_songs(name):
                vid = youtube.video_id(s["file"])
                if vid:
                    self.core.download({"yt": vid, "title": s.get("Title") or vid, "artist": s.get("Artist") or ""})
            if not n_yt:
                self.win.toast("No YouTube songs in this playlist")
            return True
        return False


# ===================================================================== downloads
class Downloads(View):
    name, title, glyph = "downloads", "Downloads", G["dl"]
    hints = [("Enter", "play"), ("R", "retry"), ("dd", "delete the file")]

    def __init__(self, win):
        super().__init__(win)
        self.rows = RowList(on_activate=self._play)
        self.widget = self.rows

    def list(self):
        return self.rows

    def shown(self):
        self.refresh("downloads")

    def refresh(self, event=None):
        if event not in (None, "downloads"):
            return
        c = self.core
        active = [j for j in c.jobs if j["state"] in ("queued", "downloading", "saving")]
        failed = [j for j in c.jobs if j["state"] == "failed"]
        saved = sorted(c.downloaded.items(), key=lambda kv: -kv[1].get("at", 0))
        rows = []
        if active:
            rows.append(("header", section("Downloading")))
            for j in active:
                state = {"queued": "waiting", "downloading": f"{int(j['pct'])}%", "saving": "saving…"}[j["state"]]
                rows.append(("item", {"job": j}, self._row(j["title"], j["artist"], badge("dl", j["pct"]), state)))
        if failed:
            rows.append(("header", section("Failed · r retries")))
            for j in failed:
                rows.append(("item", {"job": j}, self._row(j["title"], j["error"][:90], badge("failed"), "")))
        if saved:
            rows.append(("header", section(f"Saved from YouTube · {len(saved)}")))
            for yt, d in saved:
                exists = os.path.exists(d["path"])
                rows.append(("item", {"saved": yt, **d}, self._row(
                    d["title"], f"{d['artist']} · {youtube.ago(d.get('at'))} · " + d["path"].replace(os.path.expanduser("~"), "~"),
                    badge("local" if exists else "failed"), "")))
        empty = label(f"{G['dl']}\n\nNothing downloaded yet.\nD on a YouTube song saves it to your music folder.",
                      "empty", xalign=0.5, wrap=True, justify=Gtk.Justification.CENTER)
        self.rows.set_rows(rows, empty=empty)

    def _row(self, title, sub, b, right):
        t = box(label(title, "title"), label(sub, "sub"), vertical=True, hexpand=True)
        return box(label(G["dl"], "glyph dim", ellipsize=False), t, b, label(right, "dur", xalign=1, ellipsize=False),
                   spacing=10)

    def _play(self, d):
        if "saved" in d and os.path.exists(d["path"]):
            md = self.core.music_dir
            uri = os.path.relpath(d["path"], md) if d["path"].startswith(md + os.sep) else d["path"]
            self.core.add_files([uri], "play")

    def key(self, k, n, mods):
        d = self.rows.selected()
        if not d:
            return False
        if k == "Return":
            self._play(d)
            return True
        # R, not r: r cycles repeat everywhere, this row or not.
        if k == "R" and "job" in d:
            self.core.retry(d["job"])
            return True
        if k == "dd" and "saved" in d:
            self.win.confirm(f"Delete “{d['title']}” from your disk?", lambda: self.core.delete_download(d["saved"]))
            return True
        return False


# ===================================================================== right pane
class NowPane(Gtk.Box):
    """What's playing: cover, title, singers, details; on Home the next
    few songs, in the queue the current lyric line (or the lyrics, L)."""

    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add_css_class("now")
        self.set_size_request(380, -1)
        self.win, self.core = win, win.core
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vexpand=True)
        self.cover_box = Gtk.Box(halign=Gtk.Align.CENTER)
        self.title = label("", "now-title", wrap=True, lines=2)
        self.artist = label("", "now-artist", wrap=True)
        self.grid = Gtk.Grid(column_spacing=12, row_spacing=4)
        self.lyric = label("", "lyric-line", wrap=True)
        g = Gtk.GestureClick()
        g.connect("pressed", lambda *_: self.win.toggle_lyrics())
        self.lyric.add_controller(g)
        self.chips = box(spacing=6)
        self.upnext = box(vertical=True, spacing=2)
        self.nextline = label("", "dim", wrap=True)
        info = box(self.cover_box, self.title, self.artist, self.grid, self.lyric, self.chips,
                   Gtk.Box(vexpand=True), self.upnext, self.nextline, vertical=True, spacing=10)
        self.lyrics = LyricsView(self.core.seek_to)
        sc = Gtk.ScrolledWindow(vexpand=True)
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.add_css_class("noscrollbar")
        sc.set_child(info)
        self.stack.add_named(sc, "now")
        self.stack.add_named(self.lyrics, "lyrics")
        self.append(self.stack)
        self.cover_size = 250

    def set_page(self, page):
        self.stack.set_visible_child_name(page)

    def set_home(self, home):
        self.cover_size = 190 if home else 240
        self.lyric.set_visible(not home)
        self.upnext.set_visible(home)
        self.nextline.set_visible(not home)
        self.refresh()

    def refresh(self, event=None):
        c = self.core
        s = c.current
        if event in (None, "art", "song", "connection"):
            child = self.cover_box.get_first_child()
            if child:
                self.cover_box.remove(child)
            path = c.art.get("path") if s and c.art.get("for") == s["id"] else None
            pic = picture(path, self.cover_size) if path else None
            if pic is None:
                pic = label(G["note"], "cover cover-glyph", xalign=0.5, ellipsize=False)
                pic.set_size_request(self.cover_size, self.cover_size)
            self.cover_box.append(pic)
        if event in (None, "song", "queue", "player", "options", "downloads", "connection", "lyrics"):
            m = c.lyrics.get("meta") if s and c.lyrics.get("for") == s["id"] else None
            self.title.set_text((m or {}).get("title") or s["title"] if s else
                                ("Nothing playing" if c.connected else c.error or "Connecting…"))
            self.artist.set_text(", ".join((m or {}).get("artists") or []) or (s.get("artist") or s.get("channel") or "")
                                 if s else "")
            self._details(s)
            self._chips(s)
            self._upnext()
        if event in (None, "lyrics", "song"):
            self.lyrics.set(c.lyrics, key=c.lyrics.get("for"))
            self.lyric.set_visible(self.upnext.get_visible() is False and bool(c.lyrics.get("lines")))

    def _details(self, s):
        child = self.grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt
        if not s:
            return
        rows = []
        if s.get("singers") and s["singers"] != s.get("artist"):
            rows.append(("Singers", s["singers"]))
        if s.get("cast"):
            rows.append(("Starring", s["cast"]))
        m = self.core.lyrics.get("meta") if self.core.lyrics.get("for") == s["id"] else None
        if m and m.get("album"):
            rows.append(("Album", m["album"] + (f" · {m['year']}" if m.get("year") else "")))
        elif s.get("movie") or s.get("album"):
            rows.append(("Film" if s.get("movie") else "Album", s.get("movie") or s["album"]))
        if m and s.get("title") != m.get("title"):
            rows.append(("Uploaded as", s["title"]))
        if s.get("channel") and s["channel"] != s.get("artist"):
            rows.append(("Channel", s["channel"]))
        if s.get("views"):
            rows.append(("Views", f"{s['views']:,}" + (f" · {s['likes']:,} likes" if s.get("likes") else "")))
        if s.get("uploaded"):
            rows.append(("Released", f"{youtube.ago(s['uploaded'])} · {time.strftime('%d %b %Y', time.localtime(s['uploaded']))}"))
        if s.get("genre"):
            rows.append(("Genre", s["genre"]))
        kind = self.core.kind(s)
        src = {"yt": "YouTube stream", "dl": "YouTube · downloading", "local": "file"}[kind]
        if kind == "local" and s.get("format"):
            rate, bits, ch = (s["format"].split(":") + ["", "", ""])[:3]
            try:
                src += f" · {int(rate) / 1000:g} kHz" + (f" · {bits} bit" if bits.isdigit() else "")
            except ValueError:
                pass
        rows.append(("Source", src))
        for i, (k, v) in enumerate(rows):
            self.grid.attach(label(k, "kv-k", ellipsize=False), 0, i, 1, 1)
            self.grid.attach(label(v, "kv-v", hexpand=True, wrap=True, lines=2), 1, i, 1, 1)

    def _chips(self, s):
        child = self.chips.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.chips.remove(child)
            child = nxt
        c = self.core
        self.chips.append(label(f"{G['radio']}  autoplay {'on' if c.autoplay else 'off'}", "chip act" if c.autoplay else "chip",
                                ellipsize=False))
        rep = c.repeat_mode()
        if rep != "off":
            self.chips.append(label(f"repeat {rep}", "chip act", ellipsize=False))
        if c.status.get("random") == "1":
            self.chips.append(label("shuffle", "chip act", ellipsize=False))

    def _upnext(self):
        c = self.core
        p = c.cur_pos
        nxt = c.queue[p + 1:p + 4] if p >= 0 else []
        child = self.upnext.get_first_child()
        while child:
            n2 = child.get_next_sibling()
            self.upnext.remove(child)
            child = n2
        if nxt:
            self.upnext.append(label("UP NEXT", "sect"))
            for s in nxt:
                t = box(label(s["title"], "t"), label(song_meta(s) + (" · autoplay" if s["auto"] else ""), "a"),
                        vertical=True, hexpand=True)
                self.upnext.append(box(self.win.views["queue"].thumb_or_tile(s, 30), t,
                                       label(fmt_time(s["duration"]), "dur dim", ellipsize=False), spacing=10,
                                       cls="upnext-row"))
            more = len(c.queue) - p - 4
            if more > 0:
                self.upnext.append(label(f"{more} more · 1 for the full queue", "dim"))
        first = nxt[0]["title"] if nxt else ("nothing (autoplay is off)" if not c.autoplay else "lining up more…")
        self.nextline.set_markup(f"Up next: <b>{esc(first)}</b>" + (f" · then {len(c.queue) - p - 2} more"
                                                                    if p >= 0 and len(c.queue) - p - 2 > 0 else ""))

    def tick(self, t):
        if self.stack.get_visible_child_name() == "lyrics":
            self.lyrics.update(t)
        line = self.lyrics.current_text(t)
        if line:
            self.lyric.set_text(f"{G['mic']}  {line}")
