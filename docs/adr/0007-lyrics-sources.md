# 7. Lyrics from YouTube Music first, and a failure is not a miss

**Status:** Accepted  
**Date:** 2026-10-24

## Context

Most songs showed no lyrics. nāda asked one source, LRCLIB (community-made, thin for Hindi film and Pakistani music), with names guessed from YouTube titles ("ROCKSTAR: Kun Faya Kun (Full Video Song) | …" by "T-Series"). Worse, any failed request (LRCLIB answered 503s and took 5 s at times) was cached as "no lyrics" for a day. A benchmark of 24 songs found lyrics for 23 on YouTube Music (22 synced), 17 on LRCLIB, 5 on NetEase, none on Musixmatch or Genius (blocked).

## Decision

Lyrics are looked up in order: the song's .lrc file and tags, YouTube Music by the video's id (the real song, artists and LyricFind's synced lyrics), YouTube Music search, LRCLIB (exact, then search) and NetEase, the last three with YouTube Music's names when it had them. A source that can't be reached raises `Unreachable`: nothing is cached and the player asks again in 30 seconds. A real miss is cached for 6 hours, only when every source answered. python-ytmusicapi is optional: without it, LRCLIB and NetEase.

## Consequences

- Lyrics for most songs, synced, and the song's real name on screen.
- YouTube Music's endpoints aren't an official API; if they change, lyrics degrade to LRCLIB and NetEase rather than disappear.
- The lyrics panel lists every version so a wrong pick is one key away.
