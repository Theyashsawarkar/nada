# nāda -- notes for AI agents (same as CLAUDE.md)

A music player (Python + GTK 4) on top of MPD, with YouTube, lyrics,
autoplay and downloads. Its own repo, pulled into Vayu
(github.com/Theyashsawarkar/vayu, whose CLAUDE.md "Plugins" rules apply);
it must work on any desktop with MPD, without Vayu.

- `bin/nada` is the CLI: with the player running it only sends a D-Bus
  action (org.gtk.Actions on dev.vayu.Nada: toggle show hide mini quit add
  tab); `ctl`, `status` and `waybar` talk to MPD directly. `nada daemon`
  re-execs with gtk4-layer-shell in LD_PRELOAD (for the mini player).
- `nada/core.py`: the model (MPD queue/state, YouTube songs and expiring
  links, autoplay, undo, downloads, lyrics, covers). `nada/mpd.py`: the MPD
  client. `nada/youtube.py`, `nada/lyrics.py`, `nada/art.py`: blocking
  helpers, only ever called from worker threads (`core.bg`). `nada/window.py`:
  the window and the vim key engine; `nada/views.py`: the tabs and the right
  pane; `nada/mini.py`, `nada/mpris.py`.
- Never block the GTK main loop: anything that touches the network or
  yt-dlp goes through `core.bg(work, then)`; only `then` touches widgets.
  Quick MPD commands are fine on the main loop.
- Every key has a `# keybind: Nada/<scope> | <keys> | <Verb> ...` line (Vayu's
  keybinding search reads them) and a row in the README (CI checks).
- Detect, don't assume: no MPD, no yt-dlp, no layer shell, no mixer each
  mean a clear message, never a crash.
- Every change: a CHANGELOG.md entry; releases are tags with `VERSION` bumped.
  `python -m py_compile nada/*.py bin/nada` and `python -m unittest discover -s tests` must pass.
- Test live without touching the user's screen: a headless sway
  (WLR_BACKENDS=headless) with its own D-Bus session, `grim` for screenshots,
  `wtype` for keys. Set MPD's volume to 0 first: playback is real.
