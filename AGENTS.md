# Strata Agent Rules

Strata is a deterministic, governed framework for mapping, auditing, and protecting
a LookML monorepo. **Read-only always.** Never writes to prod, the LookML repo, or
any live instance.

## Collaboration Model

- `Conductor` owns workflow docs, planning artifacts, and execution gates.
- CLI agents (Codex, Gemini, Claude) act as executing agents against slice specs.
- The operator reviews handoffs, approves or redirects, starts the next session.

## The Conductor Loop

Every session: read active slice → execute bounded work → write handoff → propose next slice.
The handoff's **Exact Next Steps** field is the recommendation for the next unit of work.
The operator's role is approval, not generation.

## Authority Order

When planning or implementing work, use sources in this order:

1. This file
2. `conductor/index.md` (active slice + reading order)
3. active `conductor/slice-*.md` file
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
- **Deterministic Core (L0–L1):** No LLM, pure Python, zero tokens. These layers must never call any AI model.
- **Synthesis (L2):** Cheapest model that does the job. Evidence required for every verdict — a verdict without its evidence trail does not ship.
- **Read-only is non-negotiable:** Enforced in governance, not by convention.
- **Mode Discipline:** Use Patch mode for small targeted fixes, Slice mode for bounded feature work, Full Conductor for cross-cutting changes.

## Handoff Rules

- **Commit Anchor:** Every `handoff-log.md` entry MUST include a `Commit: [7-char-hash]` field.
- **Atomic:** Every implementation commit MUST include the corresponding handoff-log update.
- **Reality Check:** If local HEAD does not match the latest handoff hash, reconcile before writing code.
- **Thin Active Handoff:** `handoff-log.md` holds only the current block; move older entries to `handoff-archive.md`.
- **Exact Next Steps required.**
- **Gates must be checked ([x]) before marking a slice stable.**

## Testing Rules

- `python -m pytest` for all changes.
- `strata validate` must pass or be approved in the PR comment (Conductor spine soft gate).
- Focus on seams: parser↔builder↔resolver, resolver↔orphan detector, IR↔MCP tools.
- Test the happy path and critical failure modes (broken extends chains, cycles, orphan detection).

## Build

```bash
python -m pytest
strata validate
```
