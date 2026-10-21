# Changelog

Newest first. Releases are tags (`vX.Y.Z`) with `VERSION` in `nada/__init__.py`.

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
