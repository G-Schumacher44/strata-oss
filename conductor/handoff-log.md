# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — fix/list-orphans-kind (narrow strata_list_orphans kind)

Commit: c17676f
  (Implementation commit; the PR squash-merges, post-merge resolve the landed anchor with
  `gh pr view 59 --json mergeCommit`.)
Conductor Mode: patch — no version bump.
Context Budget: low
Context Loaded: AGENTS.md, conductor/AGENTS.md, handoff-log latest block, mcp/tools.py, mcp/server.py, cli/query.py, README.
Exact Next Steps: operator merges after the gate passes; no follow-up work.

### What changed

`strata_list_orphans(kind=...)` accepted `explore|field` but only view orphans are recorded, so those kinds always returned `[]` (readable as "none exist"). Narrowed to `all|view`; other values raise `ValueError` with an explicit message. MCP tool schema (`Literal`), CLI `--kind` choice, and README table kept consistent. Closes #49.

### Gates

New `test_strata_list_orphans_rejects_unsupported_kind` fails with src reverted (3 failed), passes with the fix. ruff check/format, mypy src clean; full pytest 184 passed (submodules initialized).
