# {{PROJECT_NAME}} Agent Rules

This repository uses the **Strata Conductor** workflow. Agents read this file
first, choose a mode, then execute bounded work and write a handoff.

**Read-only always.** Never writes to production systems, external APIs,
or any live instance without explicit operator authorization.

## Collaboration Model

- `Conductor` owns workflow docs, planning artifacts, and execution gates.
- AI agents (Claude, Cursor, Gemini, etc.) execute against slice specs.
- The operator reviews handoffs, approves or redirects, starts the next session.

## The Conductor Loop

Every session: read active slice → execute bounded work → write handoff → propose next slice.
The handoff's **Exact Next Steps** field is the recommendation for the next unit of work.
The operator's role is approval, not generation.

## Authority Order

When planning or implementing work, use sources in this order:

1. This file (`AGENTS.md`)
2. `conductor/index.md` (active slice + reading order)
3. Active `conductor/slice-*.md` file
4. `conductor/handoff-log.md` (latest block when resuming)

## Required Reading (start here)

1. `conductor/index.md`
2. Active slice spec (listed in index.md)
3. `conductor/handoff-log.md` — latest block only when resuming active work

## Turn 1 Rule

You MUST run the following before proposing any plan:

```
git status -sb && git log -n 5 --oneline && cat conductor/handoff-log.md
```

## Execution Rules

- **Read Code First:** Read existing code before proposing structural changes.
- **Spec Before Build:** Update or create the governing Conductor artifact before implementation.
- **Deterministic Core:** No LLM in data-pipeline layers — pure, deterministic logic only.
- **Read-only is non-negotiable:** Enforced in governance, not by convention.
- **Mode Discipline:** Use Patch mode for small targeted fixes, Slice mode for bounded
  feature work, Full Conductor for cross-cutting changes.

## Handoff Rules

- **Commit Anchor:** Every `handoff-log.md` entry MUST include a `Commit: [7-char-hash]` field.
- **Atomic:** Every implementation commit MUST include the corresponding handoff-log update.
- **Reality Check:** If local HEAD does not match the latest handoff hash, reconcile before writing code.
- **Thin Active Handoff:** `handoff-log.md` holds only the current block; move older entries to `handoff-archive.md`.
- **Exact Next Steps required.**
- **Gates must be checked ([x]) before marking a slice stable.**

## Testing Rules

- All tests must pass before writing a handoff.
- Focus on seams and boundary conditions.
- Test the happy path and critical failure modes.

## Build

```bash
# Adapt these commands to your project's test runner
python -m pytest
```
