# Handoff: fix/list-orphans-kind

Commit: resolve the landed anchor with `gh pr view <PR> --json mergeCommit` (squash-merge).
Conductor Mode: patch — interface narrowing, no version bump.

## Change

`strata_list_orphans(kind=...)` accepted `explore|field`, but `_mark_orphans` only records view
orphans, so those kinds always returned `[]` (readable as "no such orphans"). Chose narrowing over
implementing: `kind` is now `all|view`; other values raise `ValueError` with an explicit message.
Kept consistent across `mcp/tools.py` (validation), `mcp/server.py` (`Literal["all", "view"]` tool
schema), `cli/query.py` (`click.Choice` + docstring), and the README tool table. CHANGELOG
Unreleased → Fixed. Closes #49.

## Verification

- New `test_strata_list_orphans_rejects_unsupported_kind` (explore/field/bogus) fails with src
  reverted (3 failed), passes with the fix.
- Existing test asserting `field == []` replaced by an `all == view` assertion.
- ruff check/format clean, mypy src clean. Full pytest: 183 passed, 1 failed —
  `test_l1_synthesis_outputs.py::test_pdt_ledger_unused_status_unaffected_by_zombie_detection`
  fails identically on untouched origin/main (pre-existing, unrelated).
