"""~/.config/nada/config.toml (everything optional):

  [nada]
  autoplay = true          # line up more songs after yours (like YouTube)
  download_dir = "YouTube" # inside MPD's music directory
  format = "opus"          # opus (no re-encoding) | mp3 | m4a
  seek_step = 10           # seconds for , and .
  volume_step = 5
  notify = true            # a notification when the song changes (player hidden)
  opacity = 0.62           # window background: 1 solid, lower shows the blur
  music_dir = ""           # default: MPD's music_directory
"""
import os
import re
import tomllib

CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "nada", "config.toml")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "nada")
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "nada")

DEFAULTS = {
    "autoplay": True,
    "download_dir": "YouTube",
    "format": "opus",
    "seek_step": 10,
    "volume_step": 5,
    "notify": True,
    "opacity": 0.62,
    "music_dir": "",
}


def load():
    conf = dict(DEFAULTS)
    try:
        with open(CONFIG, "rb") as f:
            conf.update(tomllib.load(f).get("nada", {}))
    except FileNotFoundError:
        pass
    except tomllib.TOMLDecodeError as e:
        print(f"nada: {CONFIG}: {e}; using defaults", flush=True)
    return conf


def mpd_music_dir(client=None):
    """MPD's music_directory: asked over the local socket, else read from
    mpd.conf, else ~/Music."""
    if client is not None and client.local:
        try:
            d = client.dict("config").get("music_directory")
            if d:
                return d
        except Exception:
            pass
    for path in (os.path.expanduser("~/.config/mpd/mpd.conf"), os.path.expanduser("~/.mpdconf"), "/etc/mpd.conf"):
        try:
            for line in open(path):
                m = re.match(r'\s*music_directory\s+"([^"]+)"', line)
                if m:
                    return os.path.expanduser(m.group(1))
        except OSError:
            continue
    return os.path.expanduser("~/Music")


def ensure_dirs():
    for d in (STATE, CACHE, os.path.join(CACHE, "art"), os.path.join(CACHE, "lyrics")):
        os.makedirs(d, exist_ok=True)
