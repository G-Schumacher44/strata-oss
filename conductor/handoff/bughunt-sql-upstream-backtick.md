# Handoff — bughunt/sql-upstream-backtick

**Branch:** `bughunt/sql-upstream-backtick`  
**Date:** 2026-09-30  
**Mode:** Patch  
**Status:** Implementation complete; draft PR #33 open — awaiting operator promotion to ready-for-review

---

## Objective

Fix `_sql_upstreams()` in `src/strata/ir/resolver.py` so that BigQuery-standard backtick-quoted table names (e.g. `` `project-id.dataset.table` ``) are detected as PDT upstreams. Previously only unquoted identifiers were matched; hyphens in BQ project names are not word characters, so the existing `\b[A-Za-z_][\w.]+` regex missed them entirely, causing silent data loss in the PDT dependency graph.

## Files Changed

| File | Change |
|---|---|
| `src/strata/ir/resolver.py` | `_sql_upstreams()` (line 438): added second regex pass for backtick-quoted BQ identifiers |
| `tests/test_ir_resolver.py` | Added import of `_sql_upstreams`; added 3 regression tests |

## Current State

- Implementation merged into branch, all 135 tests passing (132 pre-existing + 3 new)
- Draft PR #33 open: `fix(ir): detect backtick-quoted BigQuery table names in PDT upstream SQL`
- CI green: `test` ✅, `pr-analysis` ✅, `review` skipped (draft)
- strata-bot Conductor validation shows 2 pre-existing failures (stale hash in handoff-log.md, missing slice-08 file) — not caused by this branch

## Risks

- None: change is purely additive (second regex pass, no modification to unquoted path)
- CTE subtraction still applies to both quoted and unquoted results

## Next Steps

1. Operator promotes PR #33 from draft to ready-for-review when satisfied
2. After merge, pre-existing Conductor stale-hash / missing-slice failures can be addressed in a separate slice
