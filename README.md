<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.svg">
    <img alt="nada" src="assets/banner-dark.svg" width="560">
  </picture>
</p>

<p align="center">
  <b>A keyboard-driven music player for your files and YouTube, with synced lyrics, autoplay and downloads.</b><br>
  Vim keys for everything. Built on MPD, styled like glass, opens on one key.
</p>

<p align="center">
  <a href="https://github.com/Theyashsawarkar/nada/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Theyashsawarkar/nada/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/Theyashsawarkar/nada/releases"><img alt="Release" src="https://img.shields.io/github/v/release/Theyashsawarkar/nada?color=f5c2e7&label=release"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-f5e0dc"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-a6e3a1">
  <img alt="GTK 4" src="https://img.shields.io/badge/GTK-4-89b4fa">
  <img alt="MPD" src="https://img.shields.io/badge/engine-MPD-cba6f7">
</p>

<p align="center">
  <img alt="nāda's Home: the lyrics of the playing song fill the left, scrolling with it; the right shows the cover, the singers, views, release date and what plays next" src="assets/screenshots/home.png" width="100%">
</p>

> *Nāda* (नाद) is Sanskrit for "sound": in Indian music theory, the
> primordial sound every note comes from.

nāda is a music player for people who live on the keyboard. Songs on your
disk and music from YouTube share one queue. Play a song and, like YouTube,
nāda lines up what comes next; reorder or remove anything with vim keys.
Lyrics scroll along with the song. If you like a YouTube song, `D` saves it
to your music folder, with its tags, cover and lyrics, while it keeps
playing. It runs on [MPD](https://www.musicpd.org), so your library, queue
and playback carry on with the window closed.

## Contents

- [Features](#features)
- [Install](#install)
- [Usage](#usage)
- [Keys](#keys)
- [Commands](#commands)
- [Configuration](#configuration)
- [Desktop integration](#desktop-integration)
- [How it works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Search everything from one key.** `/` opens a floating search over
  whatever you're on: your library answers as you type, YouTube a moment
  later, with the best match on top; `Tab` picks where to look (YouTube,
  library, playlists, commands, the list you're on). Play, play next, add
  or download without leaving the box.
- **Now is the lyrics.** The window opens on the playing song's lyrics,
  large, the current line lit and centred, scrolling with the song. Click a
  line to jump there. On the right: the cover, the song's **real name and
  artists** (from YouTube Music, not the upload's title), the album, views,
  and what's next.
- **Lyrics that show up.** Looked up in YouTube Music first (by the video
  itself: synced lyrics licensed from LyricFind), then LRCLIB and NetEase;
  a `.lrc` next to the file or lyrics in its tags come first. A source
  that can't be reached is asked again in 30 s, never remembered as "no
  lyrics". Hindi lyrics show in Latin letters (Hinglish) or Devanagari.
  `L` opens the lyrics panel: every version the sources have, which one
  fits the song's length, `[` `]` to fix the timing, `s` for the script.
- **Up next, like YouTube.** Playing a YouTube song lines up YouTube's own
  mix for it; a song from your library brings the rest of its album and
  more by that artist. The queue shows what you added and what autoplay
  added separately, refills itself as it runs low, and `M` turns it off.
- **Your queue, edited like text.** `dd` removes, `J`/`K` move a song,
  `yy`/`p` copy and paste, `V` selects several, `u` undoes, `Ctrl+r`
  redoes, and you can drag rows by their handle or click × to remove one.
- **Seek anywhere.** `,` and `.` skip 10 seconds (`3.` skips 30), the ⟲ ⟳
  buttons do the same, and the progress bar is clickable.
- **YouTube without an account.** Search it from `/`; every result shows
  its views and age, and "All YouTube results" opens the full list. Stream links expire after a few hours, so nāda remembers
  the video, not the link, and renews it before it plays.
- **Download what you like.** `D` saves a YouTube song as Opus (what
  YouTube streams, so nothing is re-encoded) into
  `~/Music/YouTube/<Artist>/<Title>.opus`, with tags, cover art and a
  `.lrc` lyrics file. When it finishes, the queue entry is swapped for the
  file in place, and playback carries on from the same second.
- **Your library in columns**, like yazi: artists, albums, genres or
  folders (`Tab`), `h`/`l` between columns, `/` searches everything.
- **Playlists** that mix files and YouTube songs: `:w name` saves the
  queue, `:e name` loads one.
- **A mini player** (`z`) in the corner, with the current lyric line.
- **Everywhere on the desktop**: MPRIS for media keys, `playerctl` and your
  phone (KDE Connect); a waybar module; `nada ctl` for scripts and key
  bindings; a notification with the cover when the song changes.
- **Never freezes**: anything slow (YouTube, lyrics, covers) runs in the
  background.

<p align="center">
  <img alt="The queue: played songs dimmed, the playing one highlighted, then your songs, then autoplay; each with its views and age" src="assets/screenshots/queue.png" width="49%">
  <img alt="The lyrics panel: every version the sources have, which fits the song's length, the script and the timing" src="assets/screenshots/lyrics-panel.png" width="49%">
</p>
<p align="center">
  <img alt="The search panel: the top result from your library, more from it, then YouTube's results, with the keys" src="assets/screenshots/search.png" width="49%">
  <img alt="The mini player: cover, title, the current lyric line, controls" src="assets/screenshots/mini.png" width="40%">
</p>

## Install

### Requirements

- Python 3.11+, PyGObject, GTK 4
- [MPD](https://www.musicpd.org) (the engine: it plays, keeps the queue and indexes your music)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube, and ffmpeg for downloads
- [python-ytmusicapi](https://github.com/sigma67/ytmusicapi) for lyrics from YouTube Music and songs' real names (without it, LRCLIB and NetEase only)
- optional: [gtk4-layer-shell](https://github.com/wmww/gtk4-layer-shell) (the mini player floats in a corner), mutagen (tags on downloads), a [Nerd Font](https://www.nerdfonts.com) for the icons

```sh
# Arch
sudo pacman -S --needed python-gobject gtk4 mpd yt-dlp ffmpeg python-ytmusicapi python-mutagen gtk4-layer-shell ttf-jetbrains-mono-nerd
systemctl --user enable --now mpd
```

MPD needs a `music_directory` and an audio output; the [Arch wiki](https://wiki.archlinux.org/title/Music_Player_Daemon)
has a five-line config. nāda finds MPD the way every MPD client does:
`MPD_HOST` / `MPD_PORT`, else MPD's socket in `$XDG_RUNTIME_DIR/mpd/socket`,
else `localhost:6600`.

### nāda

```sh
git clone https://github.com/Theyashsawarkar/nada ~/.local/share/nada
ln -s ~/.local/share/nada/bin/nada ~/.local/bin/nada
nada            # opens the player (it starts itself the first time)
```

Update with `git -C ~/.local/share/nada pull && nada quit`.

## Usage

```
nada                       open the player, or close it if it's open
nada show | hide | mini    the full player, hidden, the mini player
nada tab <name>            open on a tab: home queue library youtube playlists downloads
nada add [--next|--play] <YouTube URL | file | search words>
nada ctl toggle|play|pause|stop|next|prev
nada ctl seek +10 | seek -10 | seek 1:30
nada ctl vol +5 | vol -5 | vol 40
nada status [--json]       what's playing
nada waybar                JSON for a waybar module
nada daemon | quit         start / stop the player (MPD keeps playing)
```

The player is one resident process; `nada` only sends it a D-Bus message,
so it opens at once. `ctl`, `status` and `waybar` talk to MPD directly and
work even when the player isn't running. Closing the window (`q`, `Esc`)
only hides it: the music, autoplay and downloads carry on.

## Keys

The footer always shows the keys for where you are; `?` shows them all.
Counts work like vim: `5j`, `3.`, `2dd`. Everywhere: `/` searches, `Esc` goes back or closes,
`j`/`k` move, `Enter` does the main thing; while typing, `Ctrl+j`/`Ctrl+k` move.

| Key | Action |
|---|---|
| `Ctrl+Tab / Ctrl+Shift+Tab` | Switch to the next / previous tab (wraps around) |
| `/` | Open the search panel (your library, YouTube, playlists, : commands, this list) |
| `Ctrl+0..4` | Switch to that numbered tab at once (the number shown on it) |
| `0` | Switch to Now (the lyrics) |
| `1` | Switch to the queue |
| `2` | Switch to the library |
| `3` | Switch to playlists |
| `4` | Switch to downloads |
| `j / k` | Move down / up a song (counts work: 5j) |
| `gg / G` | Jump to the top / bottom (12G: to the 12th) |
| `Ctrl+d / Ctrl+u` | Scroll half a page down / up |
| `Space` | Toggle play / pause |
| `Enter` | Play the selected song |
| `. / ,` | Seek forward / back 10 seconds (3. = 30 s) |
| `> / <` | Play next / previous song |
| `= / -` | Raise / lower volume |
| `m` | Toggle mute |
| `s` | Toggle shuffle |
| `r` | Cycle repeat (off, all, this song) |
| `M` | Toggle autoplay (more like this after your songs) |
| `V` | Select several songs (visual mode) |
| `u` | Restore the last change (undo) |
| `Ctrl+r` | Restore an undone change (redo) |
| `n / N` | Jump to the next / previous match (after a "This list" search) |
| `:` | Run a command (:w name, :sleep 30m, :yt query…) |
| `?` | Show all keys |
| `z` | Switch to the mini player |
| `q / Esc` | Close the window (the music keeps playing) |

**Queue (`1`)**

| Key | Action |
|---|---|
| `dd` | Remove the song from the queue (V: the selection) |
| `yy` | Copy the song (yank) |
| `p / P` | Paste removed or copied songs below / above |
| `J / K` | Move the song down / up |
| `A` | Move the song to play next |
| `D` | Save the YouTube song to your music folder (download) |
| `L` | Show the lyrics on the right |
| `zz` | Jump to the song that's playing |

**Library (`2`)**

| Key | Action |
|---|---|
| `h / l` | Move between the columns |
| `Tab` | Switch between artists, albums, genres and folders |
| `a / A` | Add to the end of the queue / to play next |

**YouTube results (from `/`)**

| Key | Action |
|---|---|
| `a / A` | Add the result to the end of the queue / to play next |
| `D` | Save the result to your music folder (download) |

**Downloads (`4`)**

| Key | Action |
|---|---|
| `R` | Restart a failed download |
| `dd` | Delete the saved file (asks first) |

**Now (`0`)**

| Key | Action |
|---|---|
| `L` | Open the lyrics panel (pick a version, the script, the timing) |

**Lyrics panel (`L` on Now)**

| Key | Action |
|---|---|
| `j / k` | Move through the versions the sources have |
| `Enter` | Use these lyrics (kept for the song) |
| `s` | Switch the script: Hinglish (Latin letters) or Devanagari |
| `[ / ]` | Show the lyrics earlier / later by 0.25 s (kept for the song) |
| `Esc` | Close the lyrics panel |

**Search panel (`/`)**

| Key | Action |
|---|---|
| `Tab / Shift+Tab` | Switch where to look (all, YouTube, library, playlists, commands, this list) |
| `Ctrl+j / Ctrl+k` | Move through the results while typing |
| `Enter` | Play the result (a playlist: replace the queue; a command: run it) |
| `Ctrl+Enter` | Play the result next |
| `Shift+Enter` | Add the result to the end of the queue |
| `Ctrl+d` | Download the result (YouTube) |
| `Ctrl+u` | Clear the search box |
| `Ctrl+x` | Clear recent searches |
| `Esc` | Close the search panel |

**Mini player (`z`)**

| Key | Action |
|---|---|
| `Space` | Toggle play / pause |
| `. / ,` | Seek forward / back 10 seconds |
| `> / <` | Play next / previous song |
| `z / Enter` | Switch back to the full player |
| `q / Esc` | Close the mini player (the music keeps playing) |

## Commands

Typed after `:`, like vim.

| Command | Does |
|---|---|
| `:w <name>` | Save the queue as a playlist (YouTube songs included) |
| `:e <name>` | Replace the queue with a playlist (`:e` alone opens Playlists) |
| `:yt <search>` | Play the top YouTube result, and its mix after it |
| `:play <search>` | Play a song from your library (falls back to YouTube) |
| `:add <url or search>` | Add to the end of the queue |
| `:seek 1:30` · `:seek +30` | Jump to a time, or by an amount |
| `:vol 40` · `:vol +10` | Set or change the volume |
| `:sleep 30m` · `:sleep off` | Fade out and pause after a while |
| `:lyrics <search>` | Pick the lyrics by hand (remembered for the song) |
| `:autoplay on` · `off` | Same as `M` |
| `:dl` | Download the playing song |
| `:clear` | Empty the queue (`u` brings it back) |
| `:q` · `:qa` | Hide the window · quit the player |

## Configuration

Everything is optional, in `~/.config/nada/config.toml`:

```toml
[nada]
autoplay = true          # line up more songs after yours (M toggles it, and it's remembered)
download_dir = "YouTube" # inside MPD's music directory
format = "opus"          # opus (no re-encoding) | mp3 | m4a
seek_step = 10           # seconds for , and .
volume_step = 5
notify = true            # a notification when the song changes (while the window is hidden)
opacity = 0.62           # window background: 1 is solid, lower shows the blur behind it
                         # (unset: your varna theme's panel glass, so it matches Vyom's panels)
music_dir = ""           # default: MPD's music_directory
```

`~/.config/nada/style.css` is loaded last, to restyle anything (the default
look is Catppuccin Mocha with a mauve accent: see `nada/style.css`). With
[varna](https://github.com/Theyashsawarkar/varna) installed, nāda takes the
current theme's colours instead (`varna tool nada <theme>` gives it its own)
and restyles as soon as the theme changes.

## Desktop integration

**sway** (the same works with any compositor's key bindings):

```sh
exec nada daemon
bindsym $mod+Shift+m exec nada                       # open / hide
bindsym $mod+Mod1+space exec nada ctl toggle          # without opening anything
bindsym $mod+Mod1+period exec nada ctl next
bindsym $mod+Mod1+comma exec nada ctl prev
for_window [app_id="^dev\.vayu\.Nada$"] floating enable, resize set 1180 720, move position center
```

Media keys going through `playerctl` work as they are: nāda speaks MPRIS.
On SwayFX, `blur enable, corner_radius 20` in that `for_window` rule gives
the window its glass look; the mini player is a layer-shell surface named
`nada` (`layer_effects "nada" { blur enable; corner_radius 18; }`).

**waybar**, a module that shows what's playing (and disappears when
nothing is):

```jsonc
"custom/nada": {
  "exec": "nada waybar",
  "return-type": "json",
  "on-click": "nada ctl toggle",
  "on-click-middle": "nada ctl next",
  "on-click-right": "nada",
  "on-scroll-up": "nada ctl seek +10",
  "on-scroll-down": "nada ctl seek -10"
}
```

Its `class` is `play`, `pause` or `stopped`, to style each state.

**From other tools**: `nada add --play <url>` plays a YouTube link with its
mix after it; [raga](https://github.com/Theyashsawarkar/raga), the YouTube
search panel, uses exactly that.

## How it works

```
 raga, keys, waybar ──► nada (bin/nada: D-Bus) ──► the player process ──► MPD ──► speakers
                                                    │
                                                    ├─ yt-dlp: search, mixes, stream links, downloads
                                                    ├─ LRCLIB: lyrics
                                                    └─ MPRIS: media keys, phone, playerctl
```

- `nada/core.py` is the model: MPD's queue and state, plus what MPD doesn't
  do (YouTube songs and their expiring links, autoplay, undo, downloads,
  lyrics, covers). Slow work runs on worker threads and reports back on
  the GTK main loop.
- `nada/window.py` is the window and the vim key engine (modes, counts,
  pending operators, registers); `nada/views.py` the six tabs and the right
  pane; `nada/mini.py` the mini player; `nada/mpris.py` MPRIS.
- YouTube songs sit in MPD's queue as stream URLs, tagged with their video
  id, so other MPD clients see and play them too.

## Troubleshooting

- **"MPD isn't running".** `systemctl --user start mpd` (and `enable` it).
  nāda reconnects by itself.
- **No sound but it says it's playing.** That's MPD's audio output: check
  `audio_output` in your `mpd.conf` (PipeWire users: `type "pipewire"` or
  `"pulse"`).
- **"Volume control unavailable".** Your MPD output has no mixer; set
  `mixer_type "software"` in its `audio_output` block.
- **A YouTube song won't play.** Update yt-dlp first (`yt-dlp -U`, or your
  package manager): YouTube changes often and yt-dlp follows.
- **Wrong or missing lyrics.** `:lyrics <artist> <song>` picks them by hand.
- **Anything else.** The player's log has the details: `journalctl --user -u nada -u nada-daemon -b` (without systemd: `~/.local/state/nada/daemon.log`);
  please [open an issue](https://github.com/Theyashsawarkar/nada/issues/new/choose) with it.

## Contributing

Bug reports, ideas and pull requests are welcome: see
[CONTRIBUTING.md](CONTRIBUTING.md) for the development setup and the rules
the code follows, and [CHANGELOG.md](CHANGELOG.md) for what changed in each
release. Please report security issues privately ([SECURITY.md](SECURITY.md)).

nāda is part of [Vayu](https://github.com/Theyashsawarkar/vayu), a
keyboard-driven Wayland desktop, and works on its own on any desktop with
MPD.

## License

[MIT](LICENSE)
