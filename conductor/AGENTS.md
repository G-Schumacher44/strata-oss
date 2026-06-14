# Conductor — Local Agent Rules

**Full governance:** `GOVERNANCE.md` (root)
**Authority:** `AGENTS.md` (root) → `intent.md` → `conductor/index.md` → this file

---

## What this directory is

The workflow pipeline for Strata. Everything here governs how work gets planned,
executed, validated, and handed off — not what the code does.

## When you are working in this directory

You are either:
1. **Starting a session** — reading context, choosing mode, orienting from handoff-log
2. **Closing a session** — writing a handoff, checking gates, updating slice status
3. **Planning new work** — drafting a slice spec from the template before touching code

In all three cases: **spec before build**. Update conductor artifacts before implementation.

## Files you will touch most

| File | When |
|---|---|
| `handoff-log.md` | Every meaningful session — write the closing block |
| `index.md` | When active slice changes or phase status changes |
| `slice-*.md` | Checking gates `[x]` as work completes |
| `tracks.md` | When cross-repo coordination state changes |

## Files you should not touch without Full Conductor Mode

| File | Reason |
|---|---|
| `CONDUCTOR_MODES.md` | Governance policy — changing it changes how every agent operates |
| `README.md` | Directory contract — changing it changes the lifecycle model |
| `AGENTS.md` | This file — same reason |

## Slice lifecycle (enforce this)

```
queued → active → (all gates [x]) → review/ → (stable checkpoint) → archive/
```

- Do not mark a slice `stable` until all Acceptance Criteria are checked `[x]`
- Do not write `Status: stable` in handoff-log until `strata validate` passes
- Move to `review/` manually — do not delete active slices

## Handoff discipline

- Thin active handoff: one block in `handoff-log.md`, older blocks in `handoff-archive.md`
- Every block must have `Commit:`, `Conductor Mode:`, `Context Loaded:`, `Exact Next Steps`
- Use the Handoff Mode Block format from `CONDUCTOR_MODES.md`
