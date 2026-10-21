# 2. MPD is the engine; nāda is the interface

**Status:** Accepted  
**Date:** 2026-10-21

## Context

A music player needs gapless playback, a library index, a queue that survives restarts, and audio output handling. MPD has done this for twenty years, and Vayu already ran it.

## Decision

nāda never decodes audio. Playback, the queue and the library are MPD's; nāda talks to it over its socket and adds what MPD doesn't do.

## Consequences

- Closing nāda never stops the music; other MPD clients see the same queue.
- MPD is a required dependency.
