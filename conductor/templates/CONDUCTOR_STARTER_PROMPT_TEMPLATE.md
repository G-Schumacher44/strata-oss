# Conductor Starter Prompt

Date: YYYY-MM-DD
Status: active
Type: starter-prompt

You are working in the Strata repository under its local Conductor workflow.

## Mode Selection

Start in the smallest safe mode from `conductor/CONDUCTOR_MODES.md`:

- **Patch Mode** — narrow fix, one-file change, doc update.
- **Slice Mode** — planned work inside an existing slice spec.
- **Full Conductor Mode** — cross-layer change, new phase, IR contract change,
  cross-repo coordination, governance policy update.
- **Audit Mode** — review and assessment only; no implementation.

## Required First Reads

1. `AGENTS.md`
2. `conductor/CONDUCTOR_MODES.md`
3. `conductor/index.md`
4. `conductor/handoff-log.md` — latest block only
5. active slice or direct target files
6. `git status --short --branch`

Read more only when the selected mode or active slice requires it.

## Layer Constraints

Before modifying any layer, read its AGENTS.md:

- `src/strata/ir/AGENTS.md` — L0: zero tokens, no network, vendored lkml only
- `src/strata/mcp/AGENTS.md` — stdio only, read-only tools, no LLM
- `src/vendor/AGENTS.md` — frozen; exact vendoring steps; no submodule

## Vendoring (if required)

Clone to a temp path OUTSIDE this repo. Copy source files in. Delete the clone.
See `src/vendor/AGENTS.md` for exact steps.

## Context Hygiene

- Do not read `conductor/archive/**` or `handoff-archive.md` unless history is required.
- Read the active slice before reading every slice.
- Keep the diff bounded to the selected mode and task.

## Build

```bash
.venv/bin/pytest
strata validate
```

Both must pass before writing a handoff.

## Handoff

After meaningful work, update `conductor/handoff-log.md` with:

```
Conductor Mode: <mode>
Context Budget: <low|medium|high>
Context Loaded: <list>
Context Skipped: <list>
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no stable tag required.
```
