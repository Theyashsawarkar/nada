"""Lyrics: from the song's own .lrc file or tags, else online, best first:
YouTube Music (by the video's id: the real song, and synced lyrics
licensed from LyricFind), YouTube Music search, LRCLIB (exact, then
search), NetEase. Results are cached. Everything here blocks: call it from
a thread.

A failed request (a timeout, a server error) is not "no lyrics": find()
raises Unreachable and nothing is cached, so the next try asks again. A
real "not found" is cached for 6 hours, and only when every source
answered. A pick from the lyrics panel, and a timing offset, are kept."""
import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import VERSION, translit
from .config import CACHE

log = logging.getLogger("nada.lyrics")
UA = f"nada/{VERSION} (https://github.com/Theyashsawarkar/nada)"
TS = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")
MISS_TTL = 6 * 3600
TRIES = 2


class Unreachable(Exception):
    """Some source couldn't be asked (network, server error): try again later."""


# ===================================================================== text
def parse(text, offset=0.0):
    """{"synced": bool, "lines": [(seconds or None, text)]} from LRC or plain text.
    offset (seconds, from the lyrics panel) moves every line later."""
    lines, file_offset, synced = [], 0.0, False
    for raw in (text or "").splitlines():
        m = re.match(r"\[offset:\s*([+-]?\d+)\]", raw.strip(), re.I)
        if m:
            file_offset = int(m.group(1)) / 1000
            continue
        stamps = TS.findall(raw)
        body = TS.sub("", raw).strip()
        if stamps:
            synced = True
            for mm, ss in stamps:
                lines.append((int(mm) * 60 + float(ss.replace(":", ".")) - file_offset + offset, body))
        elif not re.match(r"^\[\w+:.*\]$", raw.strip()):   # skip [ar:...] style headers
            lines.append((None, raw.strip()))
    if synced:
        lines = sorted(((t, x) for t, x in lines if t is not None), key=lambda l: l[0])
    else:
        while lines and not lines[0][1]:
            lines.pop(0)
    return {"synced": synced, "lines": lines}


def is_synced(text):
    return bool(text and TS.search(text))


def in_script(text, script):
    """The lyrics in the script you chose: "latin" writes Devanagari in
    Latin letters (Hinglish), "native" leaves them as they are."""
    if script == "latin" and translit.has_devanagari(text):
        return translit.to_latin(text)
    return text


def other_script(text):
    """Mostly letters that are neither Latin nor Devanagari (Urdu, Gurmukhi…)."""
    letters = [ch for ch in TS.sub("", text or "") if ch.isalpha()]
    if not letters:
        return False
    odd = sum(1 for ch in letters if not ("a" <= ch.lower() <= "z" or "\u0900" <= ch <= "\u097f" or "\u00c0" <= ch <= "\u024f"))
    return odd / len(letters) > 0.5


def first_lines(text, n=3):
    out = []
    for raw in (text or "").splitlines():
        body = TS.sub("", raw).strip()
        if body and body != "♪" and not re.match(r"^\[\w+:.*\]$", body):
            out.append(body)
        if len(out) >= n:
            break
    return out


# ===================================================================== cache
def _key(song):
    """By the YouTube video when there is one (a title can be anything)."""
    if song.get("yt"):
        return "yt-" + song["yt"]
    return hashlib.sha1(f"{(song.get('artist') or '').lower()}|{(song.get('title') or '').lower()}".encode()).hexdigest()


def _cache_path(song):
    return os.path.join(CACHE, "lyrics", _key(song) + ".json")


def cached(song):
    try:
        with open(_cache_path(song)) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not d.get("text") and not d.get("manual") and time.time() - d.get("at", 0) > MISS_TTL:
        return None   # ask again: the sources grow
    return d


def save(song, entry):
    os.makedirs(os.path.join(CACHE, "lyrics"), exist_ok=True)
    old = cached(song) or {}
    entry = {**entry, "at": time.time()}
    if "offset" not in entry and old.get("offset"):
        entry["offset"] = old["offset"]
    tmp = _cache_path(song) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(entry, f, ensure_ascii=False)
    os.replace(tmp, _cache_path(song))
    return entry


def set_offset(song, offset):
    d = cached(song) or {"text": "", "source": ""}
    d["offset"] = round(offset, 2)
    save(song, d)


# ===================================================================== HTTP
def _get(url, data=None, headers=None):
    """JSON from url; a missing page is None, anything else that fails
    raises Unreachable after TRIES attempts."""
    last = None
    for attempt in range(TRIES):
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = e
        time.sleep(0.6 * (attempt + 1))
    raise Unreachable(f"{urllib.parse.urlparse(url).hostname}: {last}")


def _norm(x):
    return re.sub(r"\W+", " ", (x or "").lower()).strip()


def _strip_noise(x):
    return re.sub(r"\(.*?\)|\[.*?\]", " ", x or "")


# ===================================================================== YouTube Music
_ytm = None
_ytm_lock = threading.Lock()


def _ytmusic():
    """The YouTube Music client (python-ytmusicapi), or None without it."""
    global _ytm
    with _ytm_lock:
        if _ytm is None:
            try:
                from ytmusicapi import YTMusic
                _ytm = YTMusic()
            except ImportError:
                _ytm = False
            except Exception as e:   # its setup reaches YouTube
                raise Unreachable(f"YouTube Music: {e}") from None
        return _ytm or None


def _ytm_lyrics(ytm, browse_id):
    """(text, synced) for a YouTube Music lyrics id."""
    ly = ytm.get_lyrics(browse_id, timestamps=True)
    if not ly or not ly.get("lyrics"):
        return None, False
    if ly.get("hasTimestamps"):
        out = []
        for line in ly["lyrics"]:
            t = (getattr(line, "start_time", None) or 0) / 1000
            out.append(f"[{int(t // 60):02d}:{t % 60:05.2f}]{getattr(line, 'text', '')}")
        return "\n".join(out), True
    return ly["lyrics"], False


def _ytm_call(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:   # ytmusicapi raises its own and requests' errors
        raise Unreachable(f"YouTube Music: {type(e).__name__}") from None


def ytmusic_video(vid):
    """For a YouTube video: ({"title", "artists", "album", "year"}, text, source)
    from YouTube Music. text is None when it has no lyrics for it."""
    ytm = _ytmusic()
    if ytm is None:
        return None, None, None
    wp = _ytm_call(ytm.get_watch_playlist, vid, limit=1)
    tr = (wp.get("tracks") or [{}])[0]
    meta = None
    if tr.get("title"):
        meta = {"title": tr["title"], "artists": [a["name"] for a in tr.get("artists") or [] if a.get("name")],
                "album": (tr.get("album") or {}).get("name") or "", "year": tr.get("year") or ""}
    if not wp.get("lyrics"):
        return meta, None, None
    text, _ = _ytm_call(_ytm_lyrics, ytm, wp["lyrics"])
    return meta, text, "YouTube Music"


def ytmusic_search(title, artist, duration=0):
    """(text, source) from YouTube Music's song search, or (None, None)."""
    ytm = _ytmusic()
    if ytm is None:
        return None, None
    hits = _ytm_call(ytm.search, f"{title} {artist}".strip(), filter="songs", limit=5)
    t = _norm(_strip_noise(title))
    named = [h for h in hits or [] if (lambda n: n and (n == t or n in t or t in n))(_norm(_strip_noise(h.get("title"))))]
    # Same length first (its timing fits). A live or extended upload has no
    # same-length version: then the same song's words, without the timing.
    close = [h for h in named if not duration or not h.get("duration_seconds") or abs(h["duration_seconds"] - duration) <= 25]
    for h, timed in [(h, True) for h in close] + [(h, False) for h in named if h not in close]:
        wp = _ytm_call(ytm.get_watch_playlist, h["videoId"], limit=1)
        if wp.get("lyrics"):
            text, _ = _ytm_call(_ytm_lyrics, ytm, wp["lyrics"])
            if text:
                return (text if timed else "\n".join(first_lines(text, 10 ** 6))), "YouTube Music"
    return None, None


# ===================================================================== LRCLIB
def _pick(d):
    return d.get("syncedLyrics") or d.get("plainLyrics") or ("" if not d.get("instrumental") else "[00:00.00] ♪ instrumental")


def lrclib_get(artist, title, album="", duration=0):
    q = {"artist_name": artist, "track_name": title}
    if album:
        q["album_name"] = album
    if duration:
        q["duration"] = int(duration)
    d = _get("https://lrclib.net/api/get?" + urllib.parse.urlencode(q))
    return (_pick(d), "LRCLIB") if d and _pick(d) else (None, None)


def lrclib_candidates(query):
    """Every LRCLIB result with lyrics for a search, as candidates."""
    out = []
    for d in _get("https://lrclib.net/api/search?" + urllib.parse.urlencode({"q": query})) or []:
        text = _pick(d)
        if text:
            out.append({"source": "LRCLIB", "text": text, "synced": is_synced(text), "title": d.get("trackName") or "",
                        "artist": d.get("artistName") or "", "duration": d.get("duration") or 0})
    return out


def search_lrclib(query, duration=0, strict=True, context=""):
    """The best LRCLIB search result: (text, "LRCLIB") or (None, None).
    strict: its length must be within 8 s. Not strict (a YouTube title
    guess): the song's name must be in the query, and the length close
    unless the artist matches too."""
    best = None
    q = _norm(query)
    for c in lrclib_candidates(query):
        name = _norm(_strip_noise(c["title"]))
        if not strict and (not name or name not in q):
            continue
        artist_named = bool(c["artist"]) and _norm(c["artist"]) in _norm(context or query)
        score = (0 if artist_named else 1, 0 if name == q else 1, 0 if c["synced"] else 1,
                 abs(c["duration"] - duration) if duration else 0)
        if best is None or score < best[0]:
            best = (score, c)
    if not best:
        return None, None
    not_named, not_exact, _, diff = best[0]
    if strict and duration and diff >= 8:
        return None, None
    if not strict and duration and not_named and diff > (120 if not not_exact else 60):
        return None, None
    return best[1]["text"], "LRCLIB"


# ===================================================================== NetEase
def netease(title, artist, duration=0):
    """(text, "NetEase") or (None, None): good for international pop."""
    d = _get("https://music.163.com/api/search/pc?" + urllib.parse.urlencode({"s": f"{title} {artist}", "type": 1, "limit": 5}),
             headers={"Referer": "https://music.163.com"})
    t = _norm(_strip_noise(title))
    for s in ((d or {}).get("result") or {}).get("songs") or []:
        if _norm(_strip_noise(s.get("name"))) != t:
            continue
        if duration and s.get("duration") and abs(s["duration"] / 1000 - duration) > 10:
            continue
        ly = _get(f"https://music.163.com/api/song/lyric?id={s['id']}&lv=1", headers={"Referer": "https://music.163.com"})
        text = ((ly or {}).get("lrc") or {}).get("lyric") or ""
        if text.strip() and "纯音乐" not in text:   # "pure music": NetEase's no-lyrics placeholder
            return text, "NetEase"
    return None, None


# ===================================================================== finding
NOISE_WORDS = re.compile(r"(?i)\b(live|cover|unplugged|performance|version|official|full|song|video|lyrical|"
                         r"lyrics?|audio|hd|4k|reprise|acoustic|from|the|movie|film)\b")


def variants(title):
    """Shorter and shorter guesses at the song's own name (YouTube titles)."""
    bare = title.split(":", 1)[-1].strip()
    out = [bare, title]
    no_paren = re.sub(r"\(.*?\)|\[.*?\]", " ", bare).strip()
    out.append(no_paren)
    m = re.search(r"(?i)\b(?:singing|sings|performs|performing)\s+(.+)", no_paren)
    if m:
        out.append(m.group(1))
    for q in list(out):
        out.append(re.sub(r"\s{2,}", " ", NOISE_WORDS.sub(" ", q)).strip())
    return [q for q in dict.fromkeys(o.strip(" -|\"'") for o in out) if len(q) >= 3]


def _local(song, music_dir, client):
    f = song.get("file") or ""
    if not f or f.startswith(("http://", "https://")):
        return None, None
    path = f if f.startswith("/") else os.path.join(music_dir, f)
    lrc = os.path.splitext(path)[0] + ".lrc"
    if os.path.exists(lrc):
        return open(lrc, encoding="utf-8", errors="replace").read(), "the .lrc file"
    if client is not None:
        try:
            tags = {k.lower(): v for k, v in client.pairs("readcomments", f)}
            text = tags.get("lyrics") or tags.get("syncedlyrics") or tags.get("unsyncedlyrics")
            if text:
                return text, "the file's tags"
        except Exception:
            pass
    return None, None


def result(entry, script="latin"):
    """What the player shows: parsed lines in your script, with the source,
    the song's real name (from YouTube Music) and the timing offset."""
    text = in_script(entry.get("text") or "", script)
    return {**parse(text, entry.get("offset") or 0.0), "source": entry.get("source") or "",
            "meta": entry.get("meta"), "offset": entry.get("offset") or 0.0,
            "devanagari": translit.has_devanagari(entry.get("text") or ""), "manual": bool(entry.get("manual"))}


def find(song, music_dir="", client=None, script="latin"):
    """Lyrics for a song dict (title, artist, album, duration, file, yt).
    Returns result(); lines is empty when no source has them. Raises
    Unreachable when a source couldn't be asked (nothing is cached then)."""
    hit = cached(song)
    if hit is not None:
        return result(hit, script)
    title, artist = song.get("title") or "", song.get("artist") or ""
    duration = song.get("duration") or 0
    vid = song.get("yt") or song.get("yt_hint")
    text, source = _local(song, music_dir, client)
    meta = None
    errors = []

    def attempt(fn, *a):
        try:
            return fn(*a)
        except Unreachable as e:
            errors.append(str(e))
            log.info("lyrics: %s", e)
            return None, None
    if not text and vid:
        try:
            meta, text, source = ytmusic_video(vid)
        except Unreachable as e:
            errors.append(str(e))
    # With YouTube Music's name for the song, the other sources get the real
    # title and artist instead of the upload's.
    t = meta["title"] if meta else title
    a = (meta["artists"][0] if meta and meta["artists"] else artist)
    if not text:
        text, source = attempt(ytmusic_search, t, a, duration) if meta or not vid else (None, None)
    if not text and t:
        text, source = attempt(lrclib_get, a, t, (meta or {}).get("album") or song.get("album") or "", duration)
    if not text and t:
        text, source = attempt(search_lrclib, f"{a} {t}".strip(), duration)
    if not text and t and vid and not meta:
        # No YouTube Music match: guess the song's name from the upload's title.
        for q in variants(title):
            text, source = attempt(search_lrclib, q, duration, False, title)
            if text:
                break
    if not text and t:
        text, source = attempt(netease, t, a, duration)
    if text and script == "latin" and other_script(text):
        # Urdu, Punjabi (Gurmukhi)…: nāda can't write those in Latin
        # letters, but another source often has the same song in Latin.
        try:
            alt = [c for c in lrclib_candidates(f"{a} {t}".strip()) if not other_script(c["text"])
                   and _norm(_strip_noise(c["title"])) == _norm(_strip_noise(t))
                   and (not duration or not c["duration"] or abs(c["duration"] - duration) < 8)]
            if alt:
                alt.sort(key=lambda c: not c["synced"])
                text, source = alt[0]["text"], "LRCLIB"
        except Unreachable:
            pass
    if not text and errors:
        raise Unreachable("; ".join(errors[:2]))
    entry = save(song, {"text": text or "", "source": source or "", "meta": meta})
    return result(entry, script)


def candidates(song, music_dir="", client=None):
    """Every version the sources have, for the lyrics panel: dicts with
    source, text, synced, title, artist, duration, first (lines). The one
    in use first."""
    out, seen = [], set()
    title, artist = song.get("title") or "", song.get("artist") or ""
    duration = song.get("duration") or 0
    vid = song.get("yt") or song.get("yt_hint")

    def add(c):
        k = (c["source"], c["text"][:200])
        if c["text"] and k not in seen:
            seen.add(k)
            c["first"] = first_lines(c["text"])
            c["diff"] = abs((c.get("duration") or duration) - duration) if duration else 0
            out.append(c)
    text, source = _local(song, music_dir, client)
    if text:
        add({"source": source, "text": text, "synced": is_synced(text), "title": title, "artist": artist,
             "duration": duration})
    meta = None
    if vid:
        try:
            meta, text, source = ytmusic_video(vid)
            if text:
                add({"source": source, "text": text, "synced": is_synced(text), "title": meta["title"],
                     "artist": ", ".join(meta["artists"]), "duration": duration})
        except Unreachable:
            pass
    t = meta["title"] if meta else (variants(title)[0] if vid and variants(title) else title)
    a = meta["artists"][0] if meta and meta["artists"] else artist
    if not any(c["source"] == "YouTube Music" for c in out):
        try:
            text, source = ytmusic_search(t, a, duration)
            if text:
                add({"source": source, "text": text, "synced": is_synced(text), "title": t, "artist": a,
                     "duration": duration})
        except Unreachable:
            pass
    for q in dict.fromkeys([f"{a} {t}".strip(), t]):
        try:
            for c in lrclib_candidates(q)[:6]:
                add(c)
        except Unreachable:
            pass
    try:
        text, source = netease(t, a, duration)
        if text:
            add({"source": source, "text": text, "synced": is_synced(text), "title": t, "artist": a, "duration": duration})
    except Unreachable:
        pass
    cur = cached(song)
    if cur and cur.get("text"):
        for c in out:
            c["in_use"] = c["text"] == cur["text"]
    out.sort(key=lambda c: (not c.get("in_use"), c["diff"] > 15, not c["synced"], c["diff"]))
    return out


def use(song, cand):
    """The lyrics panel's pick: kept for good (and its timing offset)."""
    return save(song, {"text": cand["text"], "source": cand["source"], "manual": True,
                       "meta": (cached(song) or {}).get("meta")})


def write_sidecar(path, text):
    """Saves lyrics next to a downloaded song (path.lrc)."""
    if text:
        with open(os.path.splitext(path)[0] + ".lrc", "w") as f:
            f.write(text)
