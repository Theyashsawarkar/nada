"""YouTube through yt-dlp: search, stream links, mixes (what plays next)
and downloads. Everything here blocks: call it from a worker thread."""
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse

YTDLP = ["yt-dlp", "--no-warnings", "--ignore-config", "--extractor-args", "youtube:lang=en"]
BARS = re.compile(r"\s*\|\s*")
NOISE = re.compile(r"\s*[\(\[]([^)\]]*\b(official|video|lyrics?|audio|hd|4k|hq|visuali[sz]er|mv|full song|"
                   r"full video|music video|remaster(ed)?|explicit|clean)\b[^)\]]*)[\)\]]", re.I)


class YTError(Exception):
    pass


def available():
    return shutil.which("yt-dlp") is not None


def video_id(s):
    """The video id in a YouTube URL (or s itself if it is one)."""
    if re.fullmatch(r"[\w-]{11}", s or ""):
        return s
    u = urllib.parse.urlparse(s or "")
    if u.hostname and "youtu.be" in u.hostname:
        return u.path.strip("/")[:11] or None
    if u.hostname and "youtube" in u.hostname:
        q = urllib.parse.parse_qs(u.query)
        if "v" in q:
            return q["v"][0][:11]
        m = re.search(r"/(?:shorts|embed|live)/([\w-]{11})", u.path)
        if m:
            return m.group(1)
    return None


def watch_url(vid):
    return f"https://www.youtube.com/watch?v={vid}"


def thumb(vid):
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"


def clean(title, artist=""):
    """(title, artist) without the YouTube noise: "(Official Video)",
    "[4K]", "| Movie | Singers", and "Artist - Title" split up."""
    t = title or ""
    t = BARS.split(t)[0]
    t = NOISE.sub("", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" -|·")
    a = re.sub(r"\s*(- Topic|VEVO|Official)$", "", artist or "", flags=re.I).strip()
    m = re.match(r"^(.+?)\s+[-–—]\s+(.+)$", t)
    if m and (not a or m.group(1).lower() in a.lower() or a.lower() in m.group(1).lower() or len(m.group(1)) < 40):
        a, t = m.group(1).strip(), m.group(2).strip()
    return t or title, a or artist


def _run(args, timeout=60):
    try:
        r = subprocess.run(YTDLP + args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise YTError("yt-dlp isn't installed") from None
    except subprocess.TimeoutExpired:
        raise YTError("YouTube took too long to answer") from None
    if r.returncode != 0:
        err = (r.stderr.strip().splitlines() or ["yt-dlp failed"])[-1]
        raise YTError(err.replace("ERROR: ", ""))
    return r.stdout


def uploaded(d):
    """When the video came out, as a unix time (or 0)."""
    for k in ("release_timestamp", "timestamp"):
        if d.get(k):
            return int(d[k])
    for k in ("release_date", "upload_date"):
        v = d.get(k)
        if v and re.fullmatch(r"\d{8}", str(v)):
            return int(time.mktime(time.strptime(str(v), "%Y%m%d")))
    return 0


def credits(raw_title, channel=""):
    """What a YouTube title says beyond the song: the film or album
    ("ROCKSTAR: Kun Faya Kun" -> ROCKSTAR) and the people after the bars
    ("| Ranbir Kapoor | A.R. Rahman, Javed Ali" -> the last group, usually
    the singers)."""
    parts = [p.strip() for p in BARS.split(raw_title or "") if p.strip() and not p.strip().startswith(("@", "#"))]
    first = NOISE.sub("", parts[0]) if parts else ""
    movie = ""
    m = re.match(r"^([^:\-–]{2,40}):\s+\S", first)
    if m:
        movie = m.group(1).strip()
    people = ""
    rest = [p for p in parts[1:] if not re.search(r"(?i)\b(official|video|lyrics?|audio|4k|hd|full song|t-series)\b", p)]
    if rest:
        people = rest[-1]
    return {"movie": movie, "people": people, "cast": rest[0] if len(rest) > 1 else ""}


def entry(d):
    """A search/mix result as a plain dict."""
    vid = d.get("id")
    raw = d.get("title") or ""
    channel = d.get("channel") or d.get("uploader") or ""
    title, artist = clean(raw, channel)
    c = credits(raw, channel)
    return {"yt": vid, "title": title, "artist": artist, "duration": d.get("duration") or 0,
            "thumb": thumb(vid), "views": d.get("view_count") or 0, "uploaded": uploaded(d),
            "channel": channel, "singers": c["people"], "movie": c["movie"], "raw_title": raw}


def search(query, n=20):
    out = _run(["--flat-playlist", "-J", f"ytsearch{n}:{query}"], timeout=40)
    return [entry(e) for e in json.loads(out).get("entries") or [] if e.get("id") and e.get("duration")]


def mix(vid, n=25):
    """What YouTube would play after this video (its "Mix"), minus itself."""
    out = _run(["--flat-playlist", "-J", "--playlist-end", str(n + 1),
                f"https://www.youtube.com/watch?v={vid}&list=RD{vid}"], timeout=40)
    return [entry(e) for e in json.loads(out).get("entries") or [] if e.get("id") and e.get("id") != vid]


def resolve(vid):
    """A playable audio stream for the video, with its details."""
    d = json.loads(_run(["-J", "-f", "bestaudio/best", "--no-playlist", watch_url(vid)], timeout=45))
    title, artist = clean(d.get("track") or d.get("title") or "", d.get("artist") or d.get("creator")
                          or d.get("channel") or d.get("uploader") or "")
    if d.get("track") and d.get("artist"):
        title, artist = d["track"], d["artist"].split(",")[0].strip()
    url = d.get("url")
    if not url:
        raise YTError("no audio stream for this video")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    expire = int(q.get("expire", [time.time() + 5 * 3600])[0])
    channel = d.get("channel") or d.get("uploader") or ""
    c = credits(d.get("title") or "", channel)
    singers = ", ".join(d.get("artists") or []) or (d.get("artist") or "") or c["people"]
    return {"yt": vid, "url": url, "title": title, "artist": artist, "album": d.get("album") or c["movie"],
            "duration": d.get("duration") or 0, "thumb": d.get("thumbnail") or thumb(vid), "expire": expire,
            "raw_title": d.get("title") or "", "codec": d.get("acodec") or "", "abr": d.get("abr") or 0,
            "views": d.get("view_count") or 0, "likes": d.get("like_count") or 0, "uploaded": uploaded(d),
            "channel": channel, "singers": singers, "movie": c["movie"], "cast": c["cast"]}


def ago(ts):
    """'3 days ago', '1 month ago', '13 years ago' (or '')."""
    if not ts:
        return ""
    s = max(0, time.time() - ts)
    for unit, n in (("year", 365 * 86400), ("month", 30 * 86400), ("week", 7 * 86400), ("day", 86400),
                    ("hour", 3600), ("minute", 60)):
        if s >= n:
            k = int(s // n)
            return f"{k} {unit}{'s' if k > 1 else ''} ago"
    return "just now"


def views(n):
    """'1.2M views'."""
    if not n:
        return ""
    for unit, k in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= k:
            v = n / k
            return f"{v:.1f}".rstrip("0").rstrip(".") + f"{unit} views"
    return f"{n} view{'s' if n != 1 else ''}"


def safe(name):
    name = re.sub(r'[/\\:*?"<>|\x00-\x1f]', " ", name or "").strip(" .")
    return re.sub(r"\s{2,}", " ", name)[:120] or "Unknown"


def download(vid, folder, title, artist, fmt="opus", archive=None, progress=None, should_stop=None):
    """Downloads the audio into folder/<artist>/<title>.<ext> and returns
    the file's path. progress(percent) is called as it goes."""
    out_dir = os.path.join(folder, safe(artist))
    os.makedirs(out_dir, exist_ok=True)
    template = os.path.join(out_dir, safe(title) + ".%(ext)s")
    args = YTDLP + ["-f", "bestaudio/best", "-x", "--audio-format", fmt, "--audio-quality", "0",
                    "--embed-thumbnail", "--convert-thumbnails", "jpg", "--embed-metadata",
                    "--newline", "--no-playlist", "--progress-template", "download:%(progress._percent_str)s",
                    "--print", "after_move:filepath", "-o", template]
    if archive:
        args += ["--download-archive", archive]
    p = subprocess.Popen(args + [watch_url(vid)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    path, last_err = None, ""
    for line in p.stdout:
        line = line.strip()
        m = re.match(r"^\s*([\d.]+)%$", line)
        if m:
            if progress:
                progress(min(99.0, float(m.group(1))))
        elif line.startswith("/") and os.path.exists(line):
            path = line
        if should_stop and should_stop():
            p.kill()
            raise YTError("cancelled")
    err = p.stderr.read()
    p.wait()
    if p.returncode != 0:
        last_err = (err.strip().splitlines() or ["download failed"])[-1].replace("ERROR: ", "")
        raise YTError(last_err)
    if not path:   # already in the archive: find the file we made before
        for ext in (fmt, "opus", "m4a", "mp3", "webm"):
            cand = os.path.join(out_dir, safe(title) + "." + ext)
            if os.path.exists(cand):
                return cand
        raise YTError("yt-dlp skipped it (already downloaded?) and the file isn't there")
    return path
