# 4. Line up what plays next, like YouTube

**Status:** Accepted  
**Date:** 2026-10-21

## Context

Picking every next song by hand breaks listening. YouTube's mixes are good at what comes next.

## Decision

When the queue runs low, nāda adds songs: YouTube's own mix for a YouTube song, or the rest of the album and the artist for a local one. Added songs are marked autoplay and kept apart from the user's; moving one makes it the user's.

## Consequences

- Music keeps going.
- `M` turns it off, and that's remembered.
