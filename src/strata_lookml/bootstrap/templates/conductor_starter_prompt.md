# Conductor Starter Prompt — {{PROJECT_NAME}}

Date: {{DATE}}
Status: active
Type: starter-prompt

You are working in the {{PROJECT_NAME}} repository under its local Conductor workflow.

## Mode Selection

Start in the smallest safe mode from `conductor/CONDUCTOR_MODES.md`:

- **Patch Mode** — narrow fix, one-file change, doc update.
- **Slice Mode** — planned work inside an existing slice spec.
- **Full Conductor Mode** — cross-layer change, new phase, architecture decision.
- **Audit Mode** — review and assessment only; no implementation.

## Required First Reads

1. `AGENTS.md`
2. `conductor/CONDUCTOR_MODES.md`
3. `conductor/index.md`
4. `conductor/handoff-log.md` — latest block only
5. Active slice or direct target files
6. `git status --short --branch`

Read more only when the selected mode or active slice requires it.

## Context Hygiene

- Do not read `conductor/archive/**` or `handoff-archive.md` unless history is required.
- Read the active slice before reading every slice.
- Keep the diff bounded to the selected mode and task.

## Build

```bash
# Adapt to your project's test runner
python -m pytest
```

## Handoff

After meaningful work, update `conductor/handoff-log.md` with:

```
Conductor Mode: <mode>
Context Budget: <low|medium|high>
Context Loaded: <list>
Context Skipped: <list>
Tag Posture: no stable tag required.

Exact Next Steps: <one sentence>
```
