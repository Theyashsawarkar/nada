"""Cover art, cached in ~/.cache/nada/art: MPD's albumart (a cover file in
the album's folder) or readpicture (embedded), else the YouTube thumbnail.
Blocks: call from a worker thread."""
import hashlib
import os
import urllib.request

from .config import CACHE

UA = "Mozilla/5.0 (nada music player)"


def _path(key):
    return os.path.join(CACHE, "art", hashlib.sha1(key.encode()).hexdigest() + ".img")


def fetch(song, client):
    """A local image path for the song's cover, or None."""
    yt = song.get("yt")
    if yt:
        p = _path("yt:" + yt)
        if os.path.exists(p):
            return p
        for name in ("maxresdefault", "hqdefault", "mqdefault"):
            try:
                req = urllib.request.Request(f"https://i.ytimg.com/vi/{yt}/{name}.jpg", headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = r.read()
                if len(data) > 2000:
                    open(p, "wb").write(data)
                    return p
            except Exception:
                continue
        return None
    f = song.get("file") or ""
    if not f or f.startswith(("http://", "https://")):
        return None
    key = "album:" + (song.get("albumartist") or song.get("artist") or "") + "|" + (song.get("album") or "") \
        if song.get("album") else "file:" + f
    p = _path(key)
    if os.path.exists(p):
        return p if os.path.getsize(p) else None
    data = None
    for cmd in ("readpicture", "albumart"):
        try:
            data = client.picture(f, cmd)
        except Exception:
            data = None
        if data:
            break
    with open(p, "wb") as out:
        out.write(data or b"")   # empty file: we looked, there's none
    return p if data else None
