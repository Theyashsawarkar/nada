"""The player model: MPD's queue and state, plus what MPD doesn't do --
YouTube songs (fresh stream links), autoplay ("Up next"), undo, lyrics,
cover art and downloads.

MPD commands are quick and run on the GTK main loop; anything slow
(yt-dlp, the network) runs on a worker thread and reports back through
GLib.idle_add. Listeners get on_core(event) with event one of: "queue",
"player", "mixer", "options", "song" (the current song changed), "lyrics",
"art", "downloads", "connection", ("toast", text).
"""
import concurrent.futures
import json
import os
import random
import re
import subprocess
import threading
import time
from collections import deque

from gi.repository import GLib

from . import art, lyrics, youtube
from .config import CACHE, STATE, ensure_dirs, load as load_config, mpd_music_dir
from .mpd import Client, MPDError, seconds

TAG = "nada"                       # Comment tag on our YouTube entries: nada:yt:<id>
RMPC_YT = re.compile(r"/youtube/([\w-]{11})\.\w+$")


def local_date(d):
    """A file's Date tag ("2011", "2011-12-05", "20111205") as a unix time."""
    m = re.match(r"(\d{4})-?(\d{2})?-?(\d{2})?", d or "")
    if not m:
        return 0
    try:
        return int(time.mktime((int(m.group(1)), int(m.group(2) or 1), int(m.group(3) or 1), 0, 0, 0, 0, 0, -1)))
    except (OverflowError, ValueError):
        return 0


def is_stream(uri):
    return uri.startswith(("http://", "https://"))


def fmt_time(s):
    s = int(max(0, s or 0))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


class Core:
    def __init__(self):
        ensure_dirs()
        self.conf = load_config()
        self.c = Client()
        self.listeners = []
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.queue = []            # song dicts in queue order
        self.status = {}
        self.status_at = time.monotonic()
        self.connected = False
        self.error = ""
        self.music_dir = ""
        self.meta = {}             # MPD song id -> our extra info (yt, auto, thumb, expire, ...)
        self.by_uri = self._load_json("queue.json", {})   # uri -> meta, survives MPD restarts
        settings = self._load_json("settings.json", {})
        self.autoplay = settings.get("autoplay", self.conf["autoplay"])
        # Hindi (Devanagari) lyrics in Latin letters ("latin") or as written ("native")
        self.lyrics_script = settings.get("lyrics_script", "latin")
        self._lyrics_retry = None
        # Bounded: each entry keeps the songs it removed, and a long session
        # of queue edits grew these forever.
        self.undo_stack, self.redo_stack = deque(maxlen=200), deque(maxlen=200)
        self.filling = False
        self.mix_cache = {}        # seed yt id -> remaining mix entries
        self.seen_yt = set()       # yt ids already played or queued this session
        self.cur_id = None
        self.lyrics = {"synced": False, "lines": [], "source": "", "for": None, "loading": False}
        self.art = {"path": None, "for": None}
        self.jobs = []             # downloads
        self.downloaded = self._load_json("downloads.json", {})   # yt id -> {path, title, artist, at}
        self.yt_titles = self._load_json("titles.json", {})       # yt id -> [title, artist] (for playlists)
        self.dl_running = False
        self.window_visible = False
        self.muted_volume = None
        self.refreshing = set()    # song ids whose stream link is being renewed
        threading.Thread(target=self._idle_loop, daemon=True).start()

    # ------------------------------------------------------------ plumbing
    def listen(self, fn):
        self.listeners.append(fn)

    def emit(self, *events):
        for e in events:
            for fn in list(self.listeners):
                try:
                    fn(e)
                except Exception as ex:   # a broken listener mustn't break the player
                    print(f"nada: listener failed on {e}: {ex!r}", flush=True)

    def toast(self, text):
        self.emit(("toast", text))

    def bg(self, work, then=None, fail=None):
        """Runs work() on a worker thread, then then(result) or
        fail(exception) on the main loop."""
        def done(fut):
            try:
                r = fut.result()
            except Exception as e:
                # e=e: Python unbinds `e` when the except block ends, and this
                # runs later on the main loop (it was a NameError every time).
                GLib.idle_add(lambda e=e: ((fail or self._bg_failed)(e), False)[1])
                return
            if then:
                GLib.idle_add(lambda: (then(r), False)[1])
        self.pool.submit(work).add_done_callback(done)

    def _bg_failed(self, e):
        self.toast(str(e))

    def _load_json(self, name, default):
        try:
            with open(os.path.join(STATE, name)) as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    def _save_json(self, name, data):
        tmp = os.path.join(STATE, name + ".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, os.path.join(STATE, name))

    def save_settings(self):
        self._save_json("settings.json", {"autoplay": self.autoplay, "lyrics_script": self.lyrics_script})

    def cmd(self, name, *args):
        """Runs an MPD command; on failure, a toast instead of an exception."""
        try:
            return self.c.pairs(name, *args)
        except MPDError as e:
            self.toast(f"MPD: {e}")
            return None

    # ------------------------------------------------------------ MPD events
    def _idle_loop(self):
        idle = Client()
        first = True
        while True:
            try:
                if first or not idle.connected:
                    idle.connect()
                    GLib.idle_add(self._connected)
                    first = False
                changed = idle.idle("playlist", "player", "mixer", "options", "database", "stored_playlist")
                GLib.idle_add(self.refresh, set(changed))
            except Exception as e:
                idle.close()
                GLib.idle_add(self._disconnected, str(e))
                time.sleep(3)

    def _connected(self):
        self.connected, self.error = True, ""
        try:
            self.c.connect()
        except Exception as e:
            self._disconnected(str(e))
            return False
        self.music_dir = self.conf["music_dir"] or mpd_music_dir(self.c)
        self.refresh({"playlist", "player", "mixer", "options"})
        self.emit("connection")
        return False

    def _disconnected(self, why):
        if self.connected or not self.error:
            self.connected = False
            self.error = "MPD isn't running" if "No such file" in why or "refused" in why else f"Can't reach MPD: {why}"
            self.emit("connection")
        return False

    def refresh(self, changed):
        if not self.connected:
            return False
        try:
            if "playlist" in changed:
                self._load_queue()
            if changed & {"player", "mixer", "options", "playlist"}:
                self.status = self.c.status()
                self.status_at = time.monotonic()
        except MPDError:
            return False
        if "playlist" in changed:
            self.emit("queue")
        for e in ("player", "mixer", "options"):
            if e in changed:
                self.emit(e)
        cur = self.status.get("songid")
        if cur != self.cur_id:
            self.cur_id = cur
            self._song_changed()
        if changed & {"playlist", "player"}:
            self._housekeeping()
        if "stored_playlist" in changed:
            self.emit("playlists")
        if "database" in changed:
            self.emit("database")
        return False

    def _load_queue(self):
        items = self.c.queue()
        q = []
        for it in items:
            sid = it.get("Id")
            uri = it.get("file", "")
            m = self.meta.get(sid)
            if m is None:
                m = dict(self.by_uri.get(uri) or {})
                com = it.get("Comment", "")
                mm = re.match(rf"{TAG}:yt:([\w-]{{11}})(:auto)?", com)
                if mm and not m.get("yt"):
                    m.update(yt=mm.group(1), auto=bool(mm.group(2)))
                self.meta[sid] = m
            song = {
                "id": sid, "pos": int(it.get("Pos", len(q))), "file": uri,
                "title": it.get("Title") or m.get("title") or os.path.splitext(os.path.basename(uri))[0],
                "artist": it.get("Artist") or m.get("artist") or "",
                "album": it.get("Album") or m.get("album") or "",
                "albumartist": it.get("AlbumArtist", ""),
                "track": it.get("Track", ""),
                "duration": seconds(it) or m.get("duration") or 0,
                "yt": m.get("yt"), "auto": bool(m.get("auto")),
                "stream": is_stream(uri),
                "views": m.get("views") or 0, "uploaded": m.get("uploaded") or local_date(it.get("Date", "")),
                "channel": m.get("channel") or "", "singers": m.get("singers") or it.get("Performer", "") or it.get("Composer", ""),
                "movie": m.get("movie") or "", "cast": m.get("cast") or "", "likes": m.get("likes") or 0,
                "genre": it.get("Genre", ""), "format": it.get("Format", ""),
            }
            if not song["yt"]:
                r = RMPC_YT.search(uri)   # songs rmpc fetched from YouTube: their thumbnails, tidy titles
                if r:
                    song["yt_hint"] = r.group(1)
                    raw = song["title"]
                    song["title"], _ = youtube.clean(raw, song["artist"])
                    c = youtube.credits(raw)
                    song["singers"] = song["singers"] or c["people"]
                    song["movie"] = song["movie"] or c["movie"]
                    song["cast"] = song["cast"] or c["cast"]
                    song["channel"] = song["artist"]
            if song["yt"]:
                self.seen_yt.add(song["yt"])
            q.append(song)
        alive = {s["id"] for s in q}
        for sid in [k for k in self.meta if k not in alive]:
            del self.meta[sid]
        self.queue = q
        self._persist_meta()

    def _persist_meta(self):
        by_uri = {}
        for s in self.queue:
            m = self.meta.get(s["id"])
            if m:
                by_uri[s["file"]] = m
        if by_uri != self.by_uri:
            self.by_uri = by_uri
            self._save_json("queue.json", by_uri)

    # ------------------------------------------------------------ state
    @property
    def state(self):
        return self.status.get("state", "stop")

    @property
    def cur_pos(self):
        try:
            return int(self.status.get("song", -1)) if self.state != "stop" or "song" in self.status else -1
        except ValueError:
            return -1

    @property
    def current(self):
        p = self.cur_pos
        return self.queue[p] if 0 <= p < len(self.queue) else None

    def elapsed(self):
        try:
            e = float(self.status.get("elapsed", 0))
        except ValueError:
            e = 0.0
        if self.state == "play":
            e += time.monotonic() - self.status_at
        cur = self.current
        return min(e, cur["duration"]) if cur and cur["duration"] else e

    def duration(self):
        cur = self.current
        try:
            return float(self.status.get("duration") or (cur or {}).get("duration") or 0)
        except ValueError:
            return 0.0

    @property
    def volume(self):
        try:
            return int(self.status.get("volume", -1))
        except ValueError:
            return -1

    def kind(self, song):
        """'local', 'yt' (a stream) or 'dl' (downloading: with its percent)."""
        if song.get("yt"):
            job = self.job_for(song["yt"])
            if job and job["state"] in ("queued", "downloading", "saving"):
                return "dl"
            if song.get("stream"):
                return "yt"
        return "local"

    # ------------------------------------------------------------ playback
    def toggle(self):
        if self.state == "play":
            self.cmd("pause", "1")
        elif self.state == "pause":
            self.cmd("pause", "0")
        elif self.queue:
            self.cmd("play", str(max(0, self.cur_pos)))

    def play_pos(self, pos):
        if 0 <= pos < len(self.queue):
            self.cmd("play", str(pos))

    def next(self, n=1):
        target = self.cur_pos + n
        if 0 <= target < len(self.queue):
            self.cmd("play", str(target))
        else:
            self.toast("That's the end of the queue")

    def prev(self, n=1):
        if n == 1 and self.elapsed() > 4:
            self.cmd("seekcur", "0")
        else:
            self.cmd("play", str(max(0, self.cur_pos - n)))

    def seek(self, delta):
        if not self.current:
            return
        t = max(0, min(self.duration() - 1 if self.duration() else 1e9, self.elapsed() + delta))
        self.seek_to(t)

    def seek_to(self, t):
        if self.state == "stop" and self.current:
            self.cmd("seek", str(self.cur_pos), f"{max(0, t):.1f}")
        else:
            self.cmd("seekcur", f"{max(0, t):.1f}")

    def set_volume(self, v):
        if self.volume < 0:
            self.toast("MPD has no volume control for this output")
            return
        self.cmd("setvol", str(max(0, min(100, int(v)))))

    def change_volume(self, delta):
        self.set_volume(self.volume + delta)

    def mute(self):
        if self.muted_volume is None:
            self.muted_volume = self.volume
            self.set_volume(0)
            self.toast("Muted")
        else:
            self.set_volume(self.muted_volume or 50)
            self.muted_volume = None
            self.toast("Unmuted")

    def toggle_random(self):
        on = self.status.get("random") != "1"
        self.cmd("random", "1" if on else "0")
        self.toast("Shuffle on" if on else "Shuffle off")

    def cycle_repeat(self):
        """off -> all -> one -> off"""
        rep, single = self.status.get("repeat") == "1", self.status.get("single") == "1"
        if not rep:
            self.cmd("repeat", "1"), self.cmd("single", "0")
            self.toast("Repeat: all")
        elif not single:
            self.cmd("single", "1")
            self.toast("Repeat: this song")
        else:
            self.cmd("repeat", "0"), self.cmd("single", "0")
            self.toast("Repeat: off")

    def repeat_mode(self):
        if self.status.get("repeat") != "1":
            return "off"
        return "one" if self.status.get("single") == "1" else "all"

    # ------------------------------------------------------------ queue editing
    def _entry(self, song):
        """Enough to put a song back: uri, tags, our meta."""
        return {"file": song["file"], "meta": dict(self.meta.get(song["id"]) or {}),
                "tags": {"Title": song["title"], "Artist": song["artist"], "Album": song["album"]} if song["stream"] else {}}

    def _readd(self, entries, pos):
        ids = []
        for i, e in enumerate(entries):
            meta = dict(e.get("meta") or {})
            tags = dict(e.get("tags") or {})
            if meta.get("yt"):
                tags["Comment"] = f"{TAG}:yt:{meta['yt']}" + (":auto" if meta.get("auto") else "")
            try:
                sid = self.c.addid(e["file"], pos + i if pos is not None else None, tags)
            except MPDError as ex:
                self.toast(f"Couldn't add {os.path.basename(e['file'])[:40]}: {ex}")
                continue
            self.meta[sid] = meta
            ids.append(sid)
        return ids

    def delete(self, positions, record=True):
        positions = sorted({p for p in positions if 0 <= p < len(self.queue)})
        if not positions:
            return []
        removed = [(p, self._entry(self.queue[p])) for p in positions]
        ids = [self.queue[p]["id"] for p in positions]
        for sid in ids:
            self.cmd("deleteid", sid)
        if record:
            self.undo_stack.append(("delete", removed))
            self.redo_stack.clear()
        return [e for _, e in removed]

    def move(self, frm, to, record=True):
        if frm == to or not (0 <= frm < len(self.queue)) or not (0 <= to < len(self.queue)):
            return False
        song = self.queue[frm]
        was_auto = song["auto"]
        self.cmd("move", str(frm), str(to))
        if was_auto:
            self.set_auto(song["id"], False)
        if record:
            self.undo_stack.append(("move", frm, to, song["id"], was_auto))
            self.redo_stack.clear()
        return was_auto

    def put(self, entries, pos, record=True):
        """Inserts saved entries (from delete/yank) at pos."""
        for e in entries:
            e.setdefault("meta", {})["auto"] = False
        ids = self._readd(entries, pos)
        if record and ids:
            self.undo_stack.append(("add", ids, entries, pos))
            self.redo_stack.clear()
        return ids

    def clear(self):
        if not self.queue:
            return
        removed = [(s["pos"], self._entry(s)) for s in self.queue]
        self.cmd("clear")
        self.undo_stack.append(("delete", removed))
        self.redo_stack.clear()

    def set_auto(self, sid, auto):
        m = self.meta.setdefault(sid, {})
        m["auto"] = auto
        if m.get("yt"):
            try:
                self.c.run("cleartagid", sid, "Comment")
                self.c.run("addtagid", sid, "Comment", f"{TAG}:yt:{m['yt']}" + (":auto" if auto else ""))
            except MPDError:
                pass
        for s in self.queue:
            if s["id"] == sid:
                s["auto"] = auto
        self._persist_meta()

    def undo(self):
        return self._history(self.undo_stack, self.redo_stack, "Undone", "Already at the oldest change")

    def redo(self):
        return self._history(self.redo_stack, self.undo_stack, "Redone", "Already at the newest change")

    def _history(self, src, dst, done, empty):
        if not src:
            self.toast(empty)
            return False
        op = src.pop()
        if op[0] == "delete":
            for p, e in op[1]:
                self._readd([e], min(p, len(self.c.queue())))
            # the inverse of re-adding is deleting them again (by their new ids)
            q = self.c.queue()
            files = {e["file"] for _, e in op[1]}
            ids = [it["Id"] for it in q if it.get("file") in files][-len(op[1]):]
            dst.append(("add", ids, [e for _, e in op[1]], op[1][0][0]))
        elif op[0] == "add":
            ids, entries = op[1], op[2]
            q = {it["Id"]: int(it["Pos"]) for it in self.c.queue()}
            removed = [(q[i], e) for i, e in zip(ids, entries, strict=False) if i in q]
            for i in ids:
                if i in q:
                    self.cmd("deleteid", i)
            dst.append(("delete", removed))
        elif op[0] == "move":
            _, frm, to, sid, was_auto = op
            self.cmd("move", str(to), str(frm))
            if was_auto:
                self.set_auto(sid, True)
            dst.append(("move", to, frm, sid, False))
        self.toast(done)
        return True

    # ------------------------------------------------------------ adding
    def add_files(self, uris, where="end"):
        """Adds library songs. where: end | next | play."""
        pos = None if where == "end" else self.cur_pos + 1 if self.cur_pos >= 0 else 0
        entries = [{"file": u, "meta": {}} for u in uris]
        ids = self._readd(entries, pos)
        if ids:
            self.undo_stack.append(("add", ids, entries, pos))
            self.redo_stack.clear()
            if where == "play":
                self.cmd("playid", ids[0])
                self.reseed(keep_ids=set(ids))
        return ids

    def add_yt(self, entries, where="end", auto=False, quiet=False):
        """Adds YouTube videos (entries with "yt") once their stream links
        are resolved (a second or two each, in parallel, order kept)."""
        entries = [e for e in entries if e.get("yt")]
        if not entries:
            return
        if not youtube.available():
            self.toast("YouTube needs yt-dlp: sudo pacman -S yt-dlp")
            return
        if not quiet:
            self.toast(f"Getting {entries[0]['title'][:40]}…" if len(entries) == 1 else f"Getting {len(entries)} songs…")
        for e in entries:
            self.seen_yt.add(e["yt"])

        def work():
            futs = [self.pool.submit(youtube.resolve, e["yt"]) if False else None for e in entries]
            out = []
            # resolve on our own small pool (the shared one runs this very function)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                futs = [ex.submit(youtube.resolve, e["yt"]) for e in entries]
                for e, f in zip(entries, futs, strict=True):
                    try:
                        out.append(f.result())
                    except Exception as err:
                        out.append({"error": str(err), "title": e.get("title", e["yt"])})
            return out

        def then(resolved):
            ok = [r for r in resolved if "url" in r]
            bad = [r for r in resolved if "error" in r]
            if bad and not quiet:
                self.toast(f"Couldn't get {bad[0]['title'][:40]}: {bad[0]['error'][:80]}")
            if not ok:
                return
            if where == "end":
                pos = None
            else:
                try:
                    pos = int(self.c.status().get("song", -1)) + 1
                except MPDError:
                    pos = None
            new = []
            for r in ok:
                meta = {k: r.get(k) for k in ("yt", "title", "artist", "album", "duration", "thumb", "expire", "views",
                                              "likes", "uploaded", "channel", "singers", "movie", "cast")}
                meta["auto"] = auto
                new.append({"file": r["url"], "meta": meta,
                            "tags": {"Title": r["title"], "Artist": r["artist"], "Album": r["album"]}})
            ids = self._readd(new, pos)
            if not ids:
                return
            for r in ok:
                self.yt_titles[r["yt"]] = [r["title"], r["artist"]]
            if len(self.yt_titles) > 5000:
                self.yt_titles = dict(list(self.yt_titles.items())[-4000:])
            self._save_json("titles.json", self.yt_titles)
            if not auto:
                self.undo_stack.append(("add", ids, new, pos))
                self.redo_stack.clear()
            if where == "play":
                self.cmd("playid", ids[0])
                self.reseed(keep_ids=set(ids))
            elif not quiet and not auto:
                self.toast(f"{'Plays next' if where == 'next' else 'Added'}: {ok[0]['title'][:50]}"
                           + (f" and {len(ok) - 1} more" if len(ok) > 1 else ""))
        self.bg(work, then)

    def add_url(self, url, where="end"):
        vid = youtube.video_id(url)
        if vid:
            self.add_yt([{"yt": vid, "title": url}], where)
        elif is_stream(url) or url.startswith("/"):
            self.add_files([url], where)
        else:   # a search: play the top YouTube result
            def work():
                r = youtube.search(url, 1)
                if not r:
                    raise youtube.YTError(f"Nothing on YouTube for “{url}”")
                return r[0]
            self.bg(work, lambda e: self.add_yt([e], where))

    # ------------------------------------------------------------ autoplay
    def set_autoplay(self, on):
        self.autoplay = on
        self.save_settings()
        if on:
            self.toast("Autoplay on: more like this after your songs")
            self._housekeeping()
        else:
            p = self.cur_pos
            autos = [s["pos"] for s in self.queue if s["auto"] and s["pos"] > p]
            if autos:
                self.delete(autos)
            self.toast("Autoplay off: the music stops after your songs")
        self.emit("options")

    def reseed(self, keep_ids=()):
        """A song was picked to play: the autoplay songs after it were
        lined up for the previous one, so replace them."""
        try:
            q = self.c.queue()
            p = int(self.c.status().get("song", -1))
        except MPDError:
            return
        stale = [it["Id"] for it in q if int(it["Pos"]) > p and it["Id"] not in keep_ids
                 and (self.meta.get(it["Id"]) or {}).get("auto")]
        for sid in stale:
            self.cmd("deleteid", sid)
        self.mix_cache.clear()

    def _housekeeping(self):
        if not self.connected:
            return
        p = self.cur_pos
        # 1. keep the queue from growing forever: drop old played songs
        if p > 150:
            for s in self.queue[:p - 100]:
                self.cmd("deleteid", s["id"])
            return
        # 2. renew YouTube links that expire soon (the next two songs)
        for s in self.queue[max(0, p):p + 3]:
            m = self.meta.get(s["id"]) or {}
            if s["stream"] and m.get("yt") and m.get("expire", 0) < time.time() + 1800 \
                    and s["id"] not in self.refreshing and (s["pos"] != p or self.state == "stop"):
                self.renew(s)
        # 3. a stream that failed to play: renew it and play again
        err = self.status.get("error", "")
        cur = self.current
        if err and cur and cur["stream"] and cur["yt"] and cur["id"] not in self.refreshing:
            self.cmd("clearerror")
            self.renew(cur, play=True)
        # 4. autoplay
        if self.autoplay and not self.filling and self.queue:
            remaining = len(self.queue) - (p + 1) if p >= 0 else 0
            if p >= 0 and remaining < 3:
                self.fill()

    def renew(self, song, play=False):
        sid = song["id"]
        self.refreshing.add(sid)
        m = dict(self.meta.get(sid) or {})

        def then(r):
            self.refreshing.discard(sid)
            try:
                q = {it["Id"]: int(it["Pos"]) for it in self.c.queue()}
            except MPDError:
                return
            if sid not in q:
                return
            m.update(expire=r["expire"])
            new = self._readd([{"file": r["url"], "meta": m,
                                "tags": {"Title": song["title"], "Artist": song["artist"], "Album": song["album"]}}], q[sid])
            if new:
                if play:
                    self.cmd("playid", new[0])
                self.cmd("deleteid", sid)

        def fail(e):
            self.refreshing.discard(sid)
            if play:
                self.toast(f"Couldn't play {song['title'][:40]}: {e}")
        self.bg(lambda: youtube.resolve(m["yt"]), then, fail)

    def fill(self):
        """Lines up more songs like the current one at the end of the queue."""
        seed = self.current or (self.queue[-1] if self.queue else None)
        if not seed:
            return
        self.filling = True
        seed_yt = seed.get("yt") or seed.get("yt_hint")
        if seed_yt and youtube.available():
            def work():
                pool = self.mix_cache.get(seed_yt)
                if pool is None:
                    pool = youtube.mix(seed_yt, 25)
                    self.mix_cache[seed_yt] = pool
                pick = []
                while pool and len(pick) < 5:
                    e = pool.pop(0)
                    if e["yt"] not in self.seen_yt:
                        pick.append(e)
                return pick

            def then(pick):
                self.filling = False
                if pick:
                    self.add_yt(pick, "end", auto=True, quiet=True)

            def fail(e):
                self.filling = False
                print(f"nada: autoplay: {e}", flush=True)
            self.bg(work, then, fail)
            return
        uris = self._local_candidates(seed)
        self.filling = False
        if uris:
            ids = self._readd([{"file": u, "meta": {"auto": True}} for u in uris], None)
            for sid in ids:
                self.meta[sid]["auto"] = True

    def _local_candidates(self, seed, n=8):
        """The rest of the seed's album, then its artist, then anything."""
        have = {s["file"] for s in self.queue}
        out = []
        try:
            if seed.get("album"):
                tracks = self.c.items("find", "album", seed["album"])
                tracks.sort(key=lambda t: (t.get("Disc", ""), int(re.sub(r"\D.*", "", t.get("Track", "0")) or 0)))
                files = [t["file"] for t in tracks]
                if seed["file"] in files:
                    files = files[files.index(seed["file"]) + 1:]
                out += [f for f in files if f not in have]
            if len(out) < n and seed.get("artist"):
                more = [t["file"] for t in self.c.items("find", "artist", seed["artist"])]
                random.shuffle(more)
                out += [f for f in more if f not in have and f not in out]
            if len(out) < n:
                every = self.c.values("list", "file")
                random.shuffle(every)
                out += [f for f in every[:200] if f not in have and f not in out]
        except MPDError:
            pass
        return out[:n]

    # ------------------------------------------------------------ song change
    def _song_changed(self):
        cur = self.current
        self.emit("song")
        if not cur:
            return
        key = cur["id"]
        self.lyrics = {"synced": False, "lines": [], "source": "", "for": key, "loading": True}
        self.emit("lyrics")
        song = dict(cur)

        self._find_lyrics(song, key)
        art_song = dict(song, yt=song.get("yt") or song.get("yt_hint"))
        self.art = {"path": None, "for": key}
        self.emit("art")

        def got_art(path):
            if self.cur_id == key:
                self.art = {"path": path, "for": key}
                self.emit("art")
                self._notify(cur, path)
        self.bg(lambda: art.fetch(art_song, self.c), got_art, lambda e: self._notify(cur, None))

    def _notify(self, song, cover):
        if not self.conf.get("notify") or self.window_visible or self.state != "play":
            return
        args = ["notify-send", "-a", "nāda", "-h", "string:x-canonical-private-synchronous:nada",
                "-h", "string:desktop-entry:nada", "-i", cover or "audio-x-generic", song["title"], song["artist"] or ""]
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------ lyrics
    def _find_lyrics(self, song, key, prefetch=True):
        """Looks the song's lyrics up (in the background). A source that
        couldn't be reached isn't "no lyrics": it says so, and asks again
        in 30 s while the song plays."""
        if self._lyrics_retry:
            GLib.source_remove(self._lyrics_retry)
            self._lyrics_retry = None

        def got(r):
            if self.cur_id == key:
                self.lyrics = {**r, "for": key, "loading": False}
                self.emit("lyrics", "song")
                if prefetch:
                    self._prefetch_lyrics()

        def failed(e):
            if self.cur_id != key:
                return
            unreachable = isinstance(e, lyrics.Unreachable)
            self.lyrics = {"synced": False, "lines": [], "source": "", "for": key, "loading": False,
                           "error": "unreachable" if unreachable else str(e)}
            self.emit("lyrics")
            if unreachable:
                print(f"nada: lyrics for {song.get('title')!r}: {e}; trying again in 30 s", flush=True)
                self._lyrics_retry = GLib.timeout_add_seconds(30, lambda: (self._retry_lyrics(song, key), False)[1])
        self.bg(lambda: lyrics.find(song, self.music_dir, self.c, self.lyrics_script), got, failed)

    def _retry_lyrics(self, song, key):
        self._lyrics_retry = None
        if self.cur_id == key:
            self._find_lyrics(song, key, prefetch=False)

    def _prefetch_lyrics(self):
        """The next song's lyrics, ready before it starts."""
        p = self.cur_pos
        nxt = self.queue[p + 1] if 0 <= p < len(self.queue) - 1 else None
        if nxt and lyrics.cached(nxt) is None:
            song = dict(nxt)
            self.bg(lambda: lyrics.find(song, self.music_dir, self.c, self.lyrics_script), lambda r: None,
                    lambda e: None)

    def reload_lyrics(self):
        cur = self.current
        if cur:
            self._find_lyrics(dict(cur), cur["id"], prefetch=False)

    def set_lyrics_script(self, script):
        self.lyrics_script = script
        self.save_settings()
        self.reload_lyrics()

    def nudge_lyrics(self, delta):
        """Moves the lyrics' timing (kept for this song); returns the new offset."""
        cur = self.current
        if not cur:
            return 0.0
        off = round((self.lyrics.get("offset") or 0.0) + delta, 2)
        lyrics.set_offset(cur, off)
        self.reload_lyrics()
        return off

    def lyrics_candidates(self, then):
        cur = self.current
        if not cur:
            then([])
            return
        song = dict(cur)
        self.bg(lambda: lyrics.candidates(song, self.music_dir, self.c), then, lambda e: then([]))

    def use_lyrics(self, cand):
        cur = self.current
        if cur:
            lyrics.use(cur, cand)
            self.reload_lyrics()

    def search_lyrics(self, query):
        """:lyrics <search>: the best LRCLIB match for your words, kept for this song."""
        cur = self.current
        if not cur:
            return
        key = cur["id"]
        song = dict(cur)

        def work():
            text, source = lyrics.search_lrclib(query or f"{cur['artist']} {cur['title']}")
            if not text:
                raise LookupError(f"No lyrics on LRCLIB for “{query}”")
            lyrics.use(song, {"text": text, "source": source})
            return lyrics.result(lyrics.cached(song), self.lyrics_script)

        def then(r):
            if self.cur_id == key:
                self.lyrics = {**r, "for": key, "loading": False}
                self.emit("lyrics")
                self.toast("Lyrics found (and remembered for this song)")
        self.toast(f"Searching lyrics for “{query or cur['title']}”…")
        self.bg(work, then)

    def job_for(self, yt):
        for j in reversed(self.jobs):
            if j["yt"] == yt:
                return j
        return None

    def download(self, song):
        yt = song.get("yt")
        if not yt:
            self.toast("Only YouTube songs need downloading: this one is already a file")
            return
        done = self.downloaded.get(yt)
        if done and os.path.exists(done["path"]):
            self.toast(f"Already saved: {done['path'].replace(os.path.expanduser('~'), '~')}")
            self._swap_in(yt, done["path"])
            return
        job = self.job_for(yt)
        if job and job["state"] in ("queued", "downloading", "saving"):
            self.toast(f"Already downloading {song['title'][:40]}")
            return
        self.jobs.append({"yt": yt, "title": song["title"], "artist": song["artist"] or "Unknown artist",
                          "album": song.get("album") or "", "duration": song.get("duration") or 0,
                          "state": "queued", "pct": 0.0, "path": None, "error": "", "at": time.time()})
        self.toast(f"Downloading {song['title'][:40]}: it keeps playing")
        self._dl_changed()
        self._next_download()

    def retry(self, job):
        if job["state"] == "failed":
            job.update(state="queued", pct=0.0, error="")
            self._dl_changed()
            self._next_download()

    def _dl_changed(self):
        active = [{"title": j["title"], "pct": round(j["pct"])} for j in self.jobs if j["state"] in ("queued", "downloading", "saving")]
        try:
            with open(os.path.join(CACHE, "downloads.json"), "w") as f:
                json.dump(active, f)
        except OSError:
            pass
        self.emit("downloads")
        self.emit("queue")

    def _next_download(self):
        if self.dl_running:
            return
        job = next((j for j in self.jobs if j["state"] == "queued"), None)
        if not job:
            return
        self.dl_running = True
        job["state"] = "downloading"
        folder = os.path.join(self.music_dir, self.conf["download_dir"])
        last = [0.0]

        def progress(pct):
            job["pct"] = pct
            if time.monotonic() - last[0] > 0.3:
                last[0] = time.monotonic()
                GLib.idle_add(lambda: (self._dl_changed(), False)[1])

        def work():
            path = youtube.download(job["yt"], folder, job["title"], job["artist"], self.conf["format"],
                                    os.path.join(STATE, "download-archive.txt"), progress)
            job["state"] = "saving"
            GLib.idle_add(lambda: (self._dl_changed(), False)[1])
            self._tag(path, job)
            try:
                song = {"title": job["title"], "artist": job["artist"], "album": job["album"],
                        "duration": job["duration"], "yt": job["yt"]}
                lyrics.find(song)
                lyrics.write_sidecar(path, (lyrics.cached(song) or {}).get("text"))
            except Exception:
                pass
            return path

        def then(path):
            self.dl_running = False
            job.update(state="done", pct=100.0, path=path)
            self.downloaded[job["yt"]] = {"path": path, "title": job["title"], "artist": job["artist"], "at": time.time()}
            self._save_json("downloads.json", self.downloaded)
            self.toast(f"Saved to {path.replace(os.path.expanduser('~'), '~')}")
            self._dl_changed()
            self._swap_in(job["yt"], path)
            self._next_download()

        def fail(e):
            self.dl_running = False
            job.update(state="failed", error=str(e))
            self.toast(f"Download failed: {job['title'][:40]}: {str(e)[:80]}")
            self._dl_changed()
            self._next_download()
        self.bg(work, then, fail)

    def _tag(self, path, job):
        try:
            import mutagen
            f = mutagen.File(path, easy=True)
            if f is None:
                return
            f["title"] = job["title"]
            f["artist"] = job["artist"]
            if job["album"]:
                f["album"] = job["album"]
            f.save()
        except Exception as e:
            print(f"nada: tagging {path}: {e}", flush=True)

    def _swap_in(self, yt, path):
        """Replaces the queue's stream of this video with the downloaded
        file, in the same place; if it's playing, carries on from the
        same second."""
        rel = os.path.relpath(path, self.music_dir) if path.startswith(self.music_dir + os.sep) else path

        def work():
            if not rel.startswith("/"):
                self.c.run("update", os.path.dirname(rel))
                for _ in range(40):
                    if self.c.items("find", "file", rel):
                        break
                    time.sleep(0.25)
            return rel

        def then(uri):
            for s in [s for s in self.queue if s.get("yt") == yt and s["stream"]]:
                playing = s["pos"] == self.cur_pos and self.state == "play"
                at = self.elapsed()
                ids = self._readd([{"file": uri, "meta": {**(self.meta.get(s["id"]) or {}), "yt": yt, "auto": s["auto"], "expire": 0}}], s["pos"])
                if not ids:
                    continue
                if playing:
                    self.cmd("playid", ids[0])
                    self.cmd("seekcur", f"{at + 0.3:.1f}")
                self.cmd("deleteid", s["id"])
        self.bg(work, then)

    def delete_download(self, yt):
        d = self.downloaded.pop(yt, None)
        if not d:
            return
        for p in (d["path"], os.path.splitext(d["path"])[0] + ".lrc"):
            try:
                os.remove(p)
            except OSError:
                pass
        self._save_json("downloads.json", self.downloaded)
        rel = os.path.relpath(d["path"], self.music_dir)
        self.cmd("update", os.path.dirname(rel))
        self.toast(f"Deleted {d['title'][:50]}")
        self.emit("downloads")

    # ------------------------------------------------------------ playlists
    def playlists(self):
        try:
            return sorted((p for k, p in self.c.pairs("listplaylists") if k == "playlist"), key=str.lower)
        except MPDError:
            return []

    def playlist_songs(self, name):
        try:
            return self.c.items("listplaylistinfo", name)
        except MPDError:
            return []

    def save_playlist(self, name):
        name = name.strip()
        if not name:
            self.toast("Give it a name: :w <name>")
            return
        try:
            self.c.run("rm", name)
        except MPDError:
            pass
        n = 0
        for s in self.queue:
            uri = youtube.watch_url(s["yt"]) if s["stream"] and s.get("yt") else s["file"]
            try:
                self.c.run("playlistadd", name, uri)
                n += 1
            except MPDError:
                pass
        self.toast(f"Saved {n} songs as the playlist “{name}”")

    def load_playlist(self, name, where="end"):
        try:
            uris = self.c.values("listplaylist", name)
        except MPDError as e:
            self.toast(f"No playlist “{name}”: {e}")
            return
        files = [u for u in uris if not youtube.video_id(u)]
        yts = [{"yt": youtube.video_id(u), "title": u} for u in uris if youtube.video_id(u)]
        if where == "replace":
            self.clear()
            where = "end"
        if files:
            self.add_files(files, "play" if where == "play" else where)
        if yts:
            self.add_yt(yts, "end" if files else where)
        self.toast(f"Loading “{name}”: {len(uris)} songs")

    def delete_playlist(self, name):
        if self.cmd("rm", name) is not None:
            self.toast(f"Deleted the playlist “{name}”")

    # ------------------------------------------------------------ library
    def lib_list(self, kind, parent=None):
        """Library columns. kind: artists | albums(artist) | songs(artist, album) | genres |
        genre_albums(genre) | folder(path)."""
        try:
            if kind == "artists":
                names = [v for v in self.c.values("list", "albumartist") if v]
                return names or [v for v in self.c.values("list", "artist") if v]
            if kind == "genres":
                return [v for v in self.c.values("list", "genre") if v]
            if kind == "albums":
                vals = [v for v in self.c.values("list", "album", "albumartist", parent) if v]
                return vals or [v for v in self.c.values("list", "album", "artist", parent) if v]
            if kind == "genre_albums":
                return [v for v in self.c.values("list", "album", "genre", parent) if v]
            if kind == "songs":
                artist, album = parent
                songs = self.c.items("find", "albumartist", artist, "album", album) if artist else []
                if not songs:
                    songs = self.c.items("find", "artist", artist, "album", album) if artist else self.c.items("find", "album", album)
                songs.sort(key=lambda t: (t.get("Disc", ""), int(re.sub(r"\D.*", "", t.get("Track", "0")) or 0)))
                return songs
            if kind == "folder":
                return self.c.items("lsinfo", parent or "")
        except MPDError:
            return []
        return []

    def search_library(self, q):
        try:
            return self.c.items("search", "any", q, "window", "0:300")
        except MPDError:
            return []
