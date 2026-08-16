# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-08-12 — bughunt/render-chart-path-guard

**What changed:** Fixed a path guard bypass in `strata_render_chart`
(`src/strata/mcp/tools.py:259`). The original guard used
`str(resolved).startswith(str(allowed_root))`, which is a string-prefix check —
not a path-ancestor check. A sibling directory like `/tmp-evil/` passes the
check because the string starts with `/tmp`. Replaced with
`resolved.is_relative_to(r)` (Python 3.9+; project requires 3.11), which
performs a proper ancestor check. Regression test
`test_render_chart_rejects_tmp_sibling_bypass` added to `tests/test_security.py`.

**What was verified:**
- Confirmed bypass with `python3 -c` before fix: `startswith` returned `True`
  for `/tmp-evil/strata_pwned.html` against the `/tmp` allowed root.
- Full suite: 106 passed (105 existing + 1 new). `is_relative_to` correctly
  returns `False` for the same path.

**What remains / exact next step:**
- PR #14 (`bughunt/render-chart-path-guard` → `bughunt/find-field-truncation-flag`)
  is open and marked ready for review. Retarget to `dev` before merge if
  preferred. No further code changes needed.
- Remaining unfixed findings from the 2026-08-12 Bug Hunt are tracked in
  issue #15: [MEDIUM] `_sql_upstreams` regex misses single-char table names
  (`resolver.py:440`), [LOW] dead-code key `".explore_name"` when explore
  model is unresolvable (`enrich.py:78`).
- Operator action needed: review and merge PR #14.
