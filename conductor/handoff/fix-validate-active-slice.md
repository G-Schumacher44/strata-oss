# Handoff: fix/validate-active-slice

Commit: resolve the landed anchor with `gh pr view <PR> --json mergeCommit` (squash-merge).
Conductor Mode: patch — no version bump.

## Change

`get_active_slice_rel` in `cli/validate.py` used the whole remainder of the `Active slice:` line
as the path, so index.md's own annotation (`path.md (review — PR open; ...)`) made the check fail.
It now takes the first whitespace-delimited token (markdown backticks stripped). The `none ...`
sentinel still passes (first token is `none`); a genuinely missing file still fails. Closes #47.
`mcp/tools.py::strata_conductor_status` still returns the full line as `active_slice` (status
text, informational, not used as a path) — left unchanged.

## Verification

- New tests in `tests/test_cli.py` (plain, annotated, backticked, and missing-file cases).
  With src reverted: 3 failed (annotated, backticked, missing-file message); with fix: 27 passed.
- ruff check/format, mypy src clean. Full pytest: 184 passed, 1 failed —
  `test_l1_synthesis_outputs.py::test_pdt_ledger_unused_status_unaffected_by_zombie_detection`,
  failing identically on untouched origin/main (pre-existing, unrelated).
