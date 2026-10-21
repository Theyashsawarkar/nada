# 3. YouTube songs are stream URLs in MPD's queue

**Status:** Accepted  
**Date:** 2026-10-21

## Context

rmpc downloaded YouTube songs before playing them: a delay before every song, and files piling up. But YouTube's stream links expire after a few hours.

## Decision

nāda resolves the audio stream with yt-dlp and adds the URL to MPD, tagged with its video id. Before a song plays, an expiring link is renewed in place; a stream that fails is renewed and retried.

## Consequences

- Songs start in about two seconds.
- A saved queue keeps working.
- Playlists store the watch URL, not the stream.
