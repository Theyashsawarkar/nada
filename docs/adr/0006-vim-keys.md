# 6. Vim keys with modes, counts and registers

**Status:** Accepted  
**Date:** 2026-10-21

## Context

The people nāda is for edit text with vim. A player with its own key scheme is another thing to learn.

## Decision

The queue is edited like text: motions, counts, operators (`dd`, `yy`, `p`), visual mode, undo and redo, `/` search and `:` commands, with a mode line. Keys without a vim meaning get one key that doesn't clash with a motion.

## Consequences

- Fast for vim users.
- Every key is in the help (`?`) and the README.
