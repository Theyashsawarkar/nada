"""Lyrics: a .lrc file next to the song, lyrics in the file's own tags, or
LRCLIB (lrclib.net: free, open, synced lyrics). Results are cached, a
"not found" for a day. Everything here blocks: call it from a thread."""
import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request

from . import VERSION
from .config import CACHE

UA = f"nada/{VERSION} (https://github.com/Theyashsawarkar/nada)"
TS = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")


def parse(text):
    """{"synced": bool, "lines": [(seconds or None, text)]} from LRC or plain text."""
    lines, offset, synced = [], 0.0, False
    for raw in (text or "").splitlines():
        m = re.match(r"\[offset:\s*([+-]?\d+)\]", raw.strip(), re.I)
        if m:
            offset = int(m.group(1)) / 1000
            continue
        stamps = TS.findall(raw)
        body = TS.sub("", raw).strip()
        if stamps:
            synced = True
            for mm, ss in stamps:
                lines.append((int(mm) * 60 + float(ss.replace(":", ".")) - offset, body))
        elif not re.match(r"^\[\w+:.*\]$", raw.strip()):   # skip [ar:...] style headers
            lines.append((None, raw.strip()))
    if synced:
        lines = sorted(((t, x) for t, x in lines if t is not None), key=lambda l: l[0])
    else:
        while lines and not lines[0][1]:
            lines.pop(0)
    return {"synced": synced, "lines": lines}


def _key(artist, title):
    return hashlib.sha1(f"{(artist or '').lower()}|{(title or '').lower()}".encode()).hexdigest()


def _cache_path(artist, title):
    return os.path.join(CACHE, "lyrics", _key(artist, title) + ".json")


def cached(artist, title):
    try:
        with open(_cache_path(artist, title)) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not d.get("text") and time.time() - d.get("at", 0) > 86400 and not d.get("manual"):
        return None   # retry a "not found" after a day
    return d


def save(artist, title, text, source, manual=False):
    os.makedirs(os.path.join(CACHE, "lyrics"), exist_ok=True)
    with open(_cache_path(artist, title), "w") as f:
        json.dump({"text": text or "", "source": source, "at": time.time(), "manual": manual}, f)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def _pick(d):
    return d.get("syncedLyrics") or d.get("plainLyrics") or ("" if not d.get("instrumental") else "[00:00.00] ♪ instrumental")


def lrclib(artist, title, album="", duration=0):
    """(lyrics text, "LRCLIB") or (None, None)."""
    q = {"artist_name": artist, "track_name": title}
    if album:
        q["album_name"] = album
    if duration:
        q["duration"] = int(duration)
    try:
        d = _get("https://lrclib.net/api/get?" + urllib.parse.urlencode(q))
        text = _pick(d)
        if text:
            return text, "LRCLIB"
    except Exception:
        pass
    return search_lrclib(f"{artist} {title}".strip(), duration)


NOISE_WORDS = re.compile(r"(?i)\b(live|cover|unplugged|performance|version|official|full|song|video|lyrical|"
                         r"lyrics?|audio|hd|4k|reprise|acoustic|from|the|movie|film)\b")


def variants(title):
    """Shorter and shorter guesses at the song's own name."""
    bare = title.split(":", 1)[-1].strip()
    out = [bare, title]
    no_paren = re.sub(r"\(.*?\)|\[.*?\]", " ", bare).strip()
    out.append(no_paren)
    m = re.search(r"(?i)\b(?:singing|sings|performs|performing)\s+(.+)", no_paren)
    if m:
        out.append(m.group(1))
    for q in list(out):
        out.append(re.sub(r"\s{2,}", " ", NOISE_WORDS.sub(" ", q)).strip())
    return [q for q in dict.fromkeys(o.strip(" -|") for o in out) if len(q) >= 3]


def search_lrclib(query, duration=0, strict=True, context=""):
    try:
        results = _get("https://lrclib.net/api/search?" + urllib.parse.urlencode({"q": query}))
    except Exception:
        return None, None
    best = None
    norm = lambda x: re.sub(r"\W+", " ", (x or "").lower()).strip()
    q = norm(query)
    for d in results or []:
        if not _pick(d):
            continue
        name = norm(re.sub(r"\(.*?\)|\[.*?\]", " ", d.get("trackName") or ""))
        if not strict and (not name or name not in q):
            continue   # a loose guess: the song's name must be in what we searched for
        artist_named = bool(d.get("artistName")) and norm(d["artistName"]) in norm(context or query)
        exact = name == q
        score = (0 if artist_named else 1, 0 if exact else 1, 0 if d.get("syncedLyrics") else 1,
                 abs((d.get("duration") or 0) - duration) if duration else 0)
        if best is None or score < best[0]:
            best = (score, d)
    if not best:
        return None, None
    d = best[1]
    not_named, not_exact, _, diff = best[0]
    if strict and duration and diff >= 8:
        return None, None
    if not strict and duration and not_named and diff > (120 if not not_exact else 60):
        # a loose guess: by an artist the title names, or the very same name and
        # not too different in length (film videos are often cut shorter)
        return None, None
    return _pick(d), "LRCLIB"


def find(song, music_dir="", client=None):
    """Lyrics for a song dict (title, artist, album, duration, file):
    {"synced", "lines", "source"}; lines is empty when none were found."""
    title, artist = song.get("title") or "", song.get("artist") or ""
    hit = cached(artist, title)
    if hit is not None:
        return {**parse(hit["text"]), "source": hit["source"]}
    text, source = None, None
    f = song.get("file") or ""
    if f and not f.startswith(("http://", "https://")):
        path = f if f.startswith("/") else os.path.join(music_dir, f)
        lrc = os.path.splitext(path)[0] + ".lrc"
        if os.path.exists(lrc):
            text, source = open(lrc, encoding="utf-8", errors="replace").read(), "the .lrc file"
        elif client is not None:
            try:
                tags = {k.lower(): v for k, v in client.pairs("readcomments", f)}
                text = tags.get("lyrics") or tags.get("syncedlyrics") or tags.get("unsyncedlyrics")
                source = "the file's tags" if text else None
            except Exception:
                pass
    if not text and title:
        text, source = lrclib(artist, title, song.get("album") or "", song.get("duration") or 0)
    if not text and title and (song.get("yt") or song.get("yt_hint")):
        # YouTube uploads often have a label or channel as the "artist", a
        # film prefix ("MOVIE: Song") or a description ("X singing Song Live
        # (Film)"): try the song's name on its own.
        for q in variants(title):
            text, source = search_lrclib(q, song.get("duration") or 0, strict=False, context=title)
            if text:
                break
    save(artist, title, text, source or "")
    return {**parse(text), "source": source or ""}


def write_sidecar(path, text):
    """Saves lyrics next to a downloaded song (path.lrc)."""
    if text:
        with open(os.path.splitext(path)[0] + ".lrc", "w") as f:
            f.write(text)
