# Changelog

Newest first. Releases are tags (`vX.Y.Z`) with `VERSION` in `nada/__init__.py`.

## v0.2.1 -- 2026-10-24

- A tab number followed by a key that takes no count (`V`, `Esc`, `/`…),
  or a lone `1`, goes to that tab first (it ran the key on the tab you
  were on).
- Switching the search panel to Commands clears the box and lists every
  command; its thumbnails appear as they load; toasts show above it.
- Tidied unused code the linter found (no change in behaviour).

## v0.2.0 -- 2026-10-24

- **Search from anywhere** (`/`): a floating panel over whatever you're on.
  Your library answers as you type, YouTube a moment later, the best match
  on top; `Tab` picks where to look (YouTube, library, playlists, commands,
  this list), `yt `, `lib `, `pl ` and `:` narrow it as you type. `Enter`
  plays, `Ctrl+Enter` plays next, `Shift+Enter` adds, `Ctrl+d` downloads,
  without leaving the box. Recent searches when it's empty. The YouTube
  tab is gone (its full results open from the panel); tabs are now Now ·
  Queue · Library · Playlists · Downloads (`0`–`4`).
- **Lyrics that show up.** They were found for few songs: nāda asked one
  source, LRCLIB, and a failed request (a timeout, a 503) was remembered
  as "no lyrics" for a day. Now: YouTube Music first, by the video itself
  (synced lyrics licensed from LyricFind, and the song's real name and
  artists), then LRCLIB and NetEase with those names. A source that can't
  be reached is asked again in 30 s and never cached; a real miss is kept
  6 hours. The next song's lyrics load while this one plays. Needs
  python-ytmusicapi (without it: LRCLIB and NetEase).
- **Hindi in Latin letters or Devanagari**: written as Hinglish ("Kadam
  badha le") by default when a source has them in Devanagari; `s` in the
  lyrics panel switches.
- **The lyrics panel** (`L` on Now): every version the sources have, with
  whether it's synced and fits the song's length; `Enter` uses one (kept),
  `[` `]` move the timing by a quarter second (kept per song).
- **Now** shows where the lyrics came from and plain words when there are
  none ("can't reach the sources · trying again in 30 s"), never a blank;
  the right side shows the song's real name, artists and album.
- **One-row player bar** under a thin timeline (thicker, with a knob, on
  hover): what's playing on the left, the controls in the middle, time and
  volume on the right.

## v0.1.6 -- 2026-10-24

- The empty queue's hint no longer points at raga's Super+Ctrl+Shift+Y
  (Vayu dropped that key: the YouTube tab, `3`, is the way in); it
  suggests `:yt <search>` instead.

## v0.1.5 -- 2026-10-24

- **Tabs like Vyom's**: `Ctrl+Tab` / `Ctrl+Shift+Tab` cycle them and
  `Ctrl+0..5` jump to one at once, from anywhere (the search box too). A
  bare digit still switches, after a moment (it may be a count, like `5j`).
- Downloads: **`R`** restarts a failed download; it was `r`, which cycles
  repeat everywhere else, so on a failed row the same key did something else.

## v0.1.4 -- 2026-10-24

- **The same glass as Vyom's panels**: without an `opacity` of your own in
  config.toml, the window takes varna's `ui.glass` (varna 0.1.9), shared by
  Vyom, vinyasa and the notifications. Without varna: 0.62, as before.

## v0.1.3 -- 2026-10-24

- **Background failures are reported again.** Every failed background job
  (lyrics, cover art, a YouTube lookup) crashed its own error handler with
  `NameError: cannot access free variable 'e'`: the callback ran after
  Python had unbound the exception. So "no lyrics", the art-less
  notification and the error toast never showed, and the real error was
  lost.
- **Logs go to the journal.** `nada` starts the player as your
  `nada.service` if you have one, else as a transient unit (`systemd-run`):
  `journalctl --user -u nada -u nada-daemon`. Only without systemd does it
  write `~/.local/state/nada/daemon.log`, now kept under 1 MB (it grew
  forever). An exception nobody caught, in a GTK callback or a thread, is
  logged with its traceback; `NADA_DEBUG=1` adds debug messages.
- Undo/redo keep the last 200 changes (they grew without limit).
- The README, CONTRIBUTING and the bug report form point to the journal.

## v0.1.2 -- 2026-10-21

- **Follows your theme**: with [varna](https://github.com/Theyashsawarkar/varna)
  installed, nāda takes the current theme's colours (its own pick under
  `tools.nada`, else the desktop's), accent included, and restyles the
  moment the theme changes, while it plays. Without varna, nothing changes.
- Placeholder covers use the theme's colours too.

## v0.1.1 -- 2026-10-21

- A website (GitHub Pages, https://theyashsawarkar.github.io/nada/): the README as a home page, the
  changelog, and architecture decision records (`docs/adr/`), built from these files by
  `scripts/build-site.py`; CI checks the site is up to date.
- Waybar module: the bars in the accent colour; a pause sign (not flat
  bars) while paused.

## v0.1.0 -- 2026-10-21

First release.

- **Home**: the playing song's lyrics, large, synced and centred on the line
  being sung (click a line to jump there); the cover, title, singers, film
  or album, views and release age, and the next three songs on the right.
- **Queue** with played / now playing / added by you / autoplay sections;
  every row shows views and how long ago the song came out. Vim editing
  (`dd`, `J`/`K`, `yy`/`p`, `V`, `u`, `Ctrl+r`), drag to reorder, × to remove.
- **Autoplay** like YouTube: a YouTube song's own mix, or the rest of a local
  song's album and its artist; refills as the queue runs low; `M` toggles it.
- **YouTube** search (yt-dlp, no account) with views and age on each result;
  stream links are renewed before they expire, and a failed stream is
  renewed and retried.
- **Downloads** (`D`): Opus (no re-encoding) into
  `~/Music/YouTube/<Artist>/<Title>.opus` with tags, cover and a `.lrc`;
  the queue entry becomes the file in place, playback carries on.
- **Lyrics** from a `.lrc`, the file's tags or LRCLIB, with YouTube titles
  cleaned up first; `:lyrics <search>` to pick by hand.
- **Library** in columns (artists, albums, genres, folders), **playlists**
  mixing files and YouTube (`:w`, `:e`), a **mini player** (`z`), vim
  commands (`:sleep`, `:seek`, `:vol`, `:yt`, `:play`…).
- **Desktop**: MPRIS (media keys, playerctl, KDE Connect), `nada ctl`,
  `nada status`, `nada waybar`, song-change notifications.
