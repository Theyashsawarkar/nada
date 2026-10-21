# 5. A download replaces the stream in place

**Status:** Accepted  
**Date:** 2026-10-21

## Context

Saving a song you're listening to shouldn't interrupt it, and the queue shouldn't end up with both copies.

## Decision

`D` downloads with yt-dlp (Opus, no re-encoding, tags, cover, lyrics) into the music directory. When MPD has indexed the file, the stream entry is replaced by the file at the same position and, if it was playing, playback resumes at the same second.

## Consequences

- No gap, no duplicate.
- Downloads need ffmpeg.
