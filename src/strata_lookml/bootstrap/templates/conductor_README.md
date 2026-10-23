# Conductor — {{PROJECT_NAME}}

Conductor owns the workflow pipeline, planning artifacts, control-doc hierarchy,
and execution-system documentation for {{PROJECT_NAME}}.

## What Lives Here

| File / Dir | Purpose |
|---|---|
| `index.md` | Machine-first routing entry — context pack, control hierarchy, active strategy |
| `README.md` | This file — directory conventions, lifecycle model, archive policy |
| `CONDUCTOR_MODES.md` | Execution-mode contract for Patch, Slice, Full, and Audit work |
| `slice-*.md` | Active commit-sized execution artifacts |
| `master-plan-*.md` | Multi-slice initiative maps (when a phase spans many slices) |
| `templates/` | Canonical templates: slice, starter prompt |
| `review/` | Completed slices awaiting explicit review/stable disposition |
| `archive/` | Reviewed slices after stable checkpoint is cut |
| `handoff-log.md` | Current active handoff block only |
| `handoff-archive.md` | Historical handoff entries — not on the hot read path |

## Naming and Placement

- Machine-first routing stays at `conductor/index.md`.
- Active slice docs stay at `conductor/slice-*.md`.
- Multi-slice initiatives get a `conductor/master-plan-*.md`.
- Completed slices move to `conductor/review/` once all gates are checked.
- After the stable checkpoint is cut, reviewed slices move to `conductor/archive/`.
- `handoff-log.md` holds the current block only — move older entries to `handoff-archive.md`.

## Lifecycle Model

```
slice-*.md (active)
    → conductor/review/    (all gates checked [x], ready for review)
    → conductor/archive/   (stable checkpoint cut)
```

- A slice is **active** while it governs implementation or validation work.
- A slice is **review-ready** only after all Acceptance Criteria are marked `[x]`.
- Move to `review/` when checklist is complete.
- Move to `archive/` after the stable checkpoint commit is made.

## Context Hygiene

- Do not read `conductor/archive/**` or `handoff-archive.md` unless history is required.
- Read the active slice before reading every slice.
- `index.md` is the entry point — start there, not at the slice list.
