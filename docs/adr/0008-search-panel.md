# 8. One floating search panel instead of a YouTube tab

**Status:** Accepted  
**Date:** 2026-10-24

## Context

Searching meant switching to the YouTube tab, typing, and pressing Enter; the library had its own search, the queue another (`/` meant something different on each tab). Command palettes (Raycast, VS Code) and music apps (YouTube Music, Spotify) converge on one box that searches everything, answers as you type, and puts the best match first.

## Decision

`/` opens a floating panel over any tab. The library answers at once, YouTube after a 350 ms pause; sections in order: top result, library, playlists, YouTube; `Tab` switches scope, prefixes (`yt `, `lib `, `pl `, `:`) narrow it, "This list" keeps the old search in a list (`n`/`N` after it). Actions run on the selected row without leaving the box. The panel (`nada/search.py`) is the same module as drishya's.

## Consequences

- The YouTube tab is gone; its full results open as a page from the panel. Tabs renumber: Now 0, Queue 1, Library 2, Playlists 3, Downloads 4.
- The same search, keys and look in nāda and drishya.
