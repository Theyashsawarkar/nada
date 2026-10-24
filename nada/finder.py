"""What the search panel (/) finds in nāda: your library (MPD), YouTube,
playlists, commands, and the list you're on."""
import re

from . import youtube
from .core import fmt_time
from .widgets import G, label, picture, tile

SCOPES = ["All", "YouTube", "Library", "Playlists", "Commands", "This list"]
YT, LIB, LISTS, COMMANDS, HERE = 1, 2, 3, 4, 5
COMMANDS_LIST = [
    ("yt", "<search>", "All YouTube results for a search"),
    ("play", "<search>", "Play a song from your library (else YouTube)"),
    ("add", "<link or search>", "Add to the end of the queue"),
    ("w", "<name>", "Save the queue as a playlist"),
    ("e", "<name>", "Replace the queue with a playlist"),
    ("seek", "<1:30 or +30>", "Jump to a time, or by an amount"),
    ("vol", "<40 or +10>", "Volume"),
    ("sleep", "<30m or off>", "Fade out and pause after a while"),
    ("lyrics", "<search>", "Pick the lyrics by your own search"),
    ("autoplay", "<on or off>", "More songs after yours"),
    ("dl", "", "Download what's playing"),
    ("clear", "", "Empty the queue (u brings it back)"),
    ("q", "", "Hide the window"),
    ("qa", "", "Quit the player"),
]


def initials(t):
    words = [w for w in re.sub(r"[^\w\s]", " ", t or "").split() if w]
    return "".join(w[0] for w in words[:2]).upper() or "♪"


class Finder:
    scopes = SCOPES

    def __init__(self, win):
        self.win, self.core = win, win.core
        self.had_local = False

    def refresh_index(self, force=False):
        pass   # MPD indexes the library

    # ------------------------------------------------------------ panel API
    def prefix(self, text):
        if text.startswith(":"):
            return COMMANDS, text[1:]
        m = re.match(r"^(yt|lib|pl)\s+(.*)$", text, re.S)
        if m:
            return {"yt": YT, "lib": LIB, "pl": LISTS}[m.group(1)], m.group(2)
        return None, text

    def wants_remote(self, q, scope):
        return scope in (0, YT) and len(q.strip()) >= 2 and youtube.available() and not q.startswith(("http://", "https://"))

    def _lead(self, song, size=40):
        path = self.win.thumb(song)
        key = song.get("yt") or song.get("file") or song.get("title")

        def make():
            return (picture(path, size, "tile") if path else None) or tile(key, song.get("title"), size)
        return make

    def _lib_song(self, d, top=False):
        song = {"file": d.get("file"), "title": d.get("Title") or (d.get("file") or "").rsplit("/", 1)[-1],
                "artist": d.get("Artist") or "", "album": d.get("Album") or ""}
        dur = d.get("duration") or d.get("Time")
        try:
            dur = float(dur)
        except (TypeError, ValueError):
            dur = 0
        return {"kind": "file", "file": song["file"], "title": song["title"],
                "sub": " · ".join(x for x in (song["artist"], song["album"]) if x), "badge": ("on disk", "local"),
                "dur": fmt_time(dur) if dur else "", "lead": self._lead(song, 72 if top else 40)}

    def _yt_song(self, e, top=False):
        sub = [e.get("artist") or e.get("channel") or "", youtube.views(e.get("views")), youtube.ago(e.get("uploaded"))]
        return dict(e, kind="yt", sub=" · ".join(x for x in sub if x), badge=("YouTube", "yt"),
                    dur=fmt_time(e["duration"]) if e.get("duration") else "",
                    lead=self._lead({"yt": e["yt"], "title": e.get("title")}, 72 if top else 40))

    def instant(self, q, scope):
        words = q.lower().split()
        if scope == COMMANDS:
            name = q.split(" ", 1)[0].lower()
            hits = [c for c in COMMANDS_LIST if c[0].startswith(name)] if name else COMMANDS_LIST
            return [{"title": "Commands", "right": "Enter runs · one that needs more fills the box",
                     "items": [{"kind": "command", "cmd": c[0], "typed": q, "needs": c[1],
                                "title": f":{c[0]} {c[1]}".strip(), "sub": c[2],
                                "lead": lambda: label(":", "glyph search-lead-glyph", ellipsize=False)} for c in hits]}]
        if scope == HERE:
            tab = self.win.tab
            return [{"title": f"Search in {self.win.views[tab].title}", "items": [
                {"kind": "here", "query": q, "title": f"Find “{q}” in {self.win.views[tab].title}" if q else "Type what to find",
                 "sub": "Enter jumps to the first match · n / N to the next ones",
                 "lead": lambda: label(G["search"], "glyph search-lead-glyph", ellipsize=False),
                 "acts": [("Enter", "find")]}]}]
        if q.startswith(("http://", "https://")):
            return [{"title": "Link", "top": True, "items": [
                {"kind": "link", "url": q.strip(), "title": "Play this link", "sub": q.strip()[:80],
                 "lead": lambda: label(G["play"], "glyph search-link-glyph", ellipsize=False),
                 "acts": [("Enter", "play"), ("Ctrl+Enter", "next")]}]}]
        secs = []
        lib = []
        if scope in (0, LIB) and words:
            lib = [d for d in self.core.search_library(q) if d.get("file")][:8 if scope else 5]
        lists = []
        if scope in (0, LISTS) and words:
            lists = [p for p in self.core.playlists() if all(w in p.lower() for w in words)][:6]
        self.had_local = bool(lib)
        if scope == 0 and lib:
            secs.append({"title": "Top result", "top": True, "items": [self._lib_song(lib[0], top=True)]})
            lib = lib[1:]
        if lib:
            secs.append({"title": "In your library", "items": [self._lib_song(d) for d in lib]})
        if lists:
            secs.append({"title": "Playlists", "items": [
                {"kind": "playlist", "name": p, "title": p, "sub": "Playlist · Enter replaces the queue, Shift+Enter adds it",
                 "badge": ("playlist", "dl"), "lead": lambda p=p: tile("pl:" + p, p, 40)} for p in lists]})
        return secs

    def remote(self, q, scope):
        results = youtube.search(q, 10 if scope == 0 else 20)
        items = [self._yt_song(r) for r in results]
        secs = []
        if items and scope == 0 and not self.had_local:
            secs.append({"title": "Top result", "top": True, "items": [self._yt_song(results[0], top=True)]})
            items = items[1:]
        if items:
            items.append({"kind": "more", "query": q, "title": f"All YouTube results for “{q}”",
                          "sub": "opens them as a page", "lead": lambda: label(G["yt"], "glyph search-lead-glyph",
                                                                               ellipsize=False)})
            secs.append({"title": "YouTube", "right": "Ctrl+d downloads", "items": items})
        return secs

    def home(self):
        c = self.core
        p = c.cur_pos
        nxt = c.queue[p + 1:p + 5] if p >= 0 else c.queue[:4]
        out = []
        if nxt:
            out.append({"title": "Up next in your queue", "items": [
                {"kind": "queued", "pos": s["pos"], "title": s["title"], "sub": s.get("artist") or "",
                 "dur": fmt_time(s["duration"]) if s.get("duration") else "", "lead": self._lead(s)} for s in nxt]})
        lists = c.playlists()[:4]
        if lists:
            out.append({"title": "Your playlists", "items": [
                {"kind": "playlist", "name": p, "title": p, "sub": "Playlist", "badge": ("playlist", "dl"),
                 "lead": lambda p=p: tile("pl:" + p, p, 40)} for p in lists]})
        if not out:
            out.append({"title": "Try", "items": [], "note": "Type to search your library and YouTube. "
                                                          "Tab picks where to look; : lists commands."})
        return out

    def act(self, it, how):
        """Does it; True keeps the panel open."""
        c, w = self.core, self.win
        kind = it.get("kind")
        where = {"play": "play", "next": "next", "add": "end"}.get(how)
        if kind == "command":
            typed = it.get("typed", "").strip()
            name = typed.split(" ", 1)[0]
            if it["needs"] and not (name == it["cmd"] and " " in typed):
                w.search.entry.set_text(f":{it['cmd']} ")
                w.search.entry.set_position(-1)
                return True
            w.command(typed if name == it["cmd"] else it["cmd"])
            return False
        if kind == "here":
            if it.get("query"):
                w.views[w.tab].search(it["query"])
            return False
        if kind == "more":
            w.switch("youtube")
            w.views["youtube"].search(it["query"])
            return False
        if kind == "queued":
            if how == "play":
                c.play_pos(it["pos"])
            return False
        if kind == "playlist":
            c.load_playlist(it["name"], "replace" if how == "play" else "end")
            return False
        if kind == "link":
            c.add_url(it["url"], where or "play")
            return False
        if how == "download":
            if kind == "yt":
                c.download(it)
            else:
                c.toast("That song is already on your disk")
            return False
        if kind == "file":
            c.add_files([it["file"]], where or "play")
        elif kind == "yt":
            c.add_yt([{k: v for k, v in it.items() if k not in ("lead", "badge", "sub", "dur", "kind")}], where or "play")
        if where in ("next", "end"):
            c.toast(f"“{it.get('title', '')[:50]}” {'plays next' if where == 'next' else 'added to the queue'}")
        return False
