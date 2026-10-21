# Contributing to nāda

Thanks for wanting to make nāda better. Bug reports, ideas and pull
requests are all welcome.

## Reporting a bug

Open an [issue](https://github.com/Theyashsawarkar/nada/issues/new/choose)
with what you did, what you expected, `nada --version`, `yt-dlp --version`,
and anything relevant from `~/.local/state/nada/daemon.log`.

## Development setup

```sh
git clone https://github.com/Theyashsawarkar/nada ~/code/nada
ln -sfn ~/code/nada/bin/nada ~/.local/bin/nada
nada quit; nada                 # restart the player with your code
python -m py_compile nada/*.py bin/nada
python -m unittest discover -s tests
```

You need MPD running (`systemctl --user start mpd`). Set its volume to 0
(`nada ctl vol 0`) while testing: playback is real.

## How it fits together

- `bin/nada`: the command line. With the player running it only sends a
  D-Bus action, so it never loads GTK; `ctl`, `status` and `waybar` talk to
  MPD directly.
- `nada/core.py`: the model: MPD's queue and state plus what MPD doesn't do
  (YouTube songs and their expiring links, autoplay, undo, downloads,
  lyrics, covers).
- `nada/window.py`: the window and the vim key engine. `nada/views.py`: the
  six tabs and the right pane. `nada/mini.py`, `nada/mpris.py`.
- `nada/mpd.py`, `nada/youtube.py`, `nada/lyrics.py`, `nada/art.py`: helpers.

## Rules

- **Never block the GTK main loop.** Network and yt-dlp calls go through
  `core.bg(work, then)`; only `then` touches widgets.
- **Every key is discoverable**: a `# keybind: Nada/<scope> | <keys> | <Verb> <object>`
  line next to it and a row in the README's key tables (CI checks).
- **Detect, don't assume**: a missing tool, MPD down or no mixer means a
  clear message, never a crash.
- **Works without Vayu**, on any desktop with MPD.
- Every change gets a `CHANGELOG.md` entry; releases are tags `vX.Y.Z` with
  `VERSION` in `nada/__init__.py` bumped.

## Pull requests

Keep them focused, describe what and why, and tick the checklist in the
template. By contributing you agree your work is released under the
[MIT License](LICENSE).
