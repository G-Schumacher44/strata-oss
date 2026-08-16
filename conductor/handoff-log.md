# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-08-12 — bughunt/render-chart-path-guard

**What changed:** Fixed a path guard bypass in `strata_render_chart`
(`src/strata/mcp/tools.py:259`). The original guard used
`str(resolved).startswith(str(allowed_root))`, a string-prefix check that
a sibling directory like `/tmp-evil/` bypasses because the string starts with
`/tmp`. Replaced with `resolved.is_relative_to(r)` (Python 3.9+; project
requires 3.11). Regression test `test_render_chart_rejects_tmp_sibling_bypass`
added to `tests/test_security.py`.

**What was verified:**
- Confirmed bypass with a one-liner before fix: `startswith` returned `True`
  for `/tmp-evil/strata_pwned.html` against the `/tmp` allowed root.
- Full suite: 106 passed (105 existing + 1 new).

**Exact Next Steps:**
- PR #14 (`bughunt/render-chart-path-guard` → `bughunt/find-field-truncation-flag`)
  is open and clean. Retarget base to `dev` before merging if preferred.
- No further code changes needed on this fix.
- Remaining unfixed findings from the 2026-08-12 Bug Hunt are in issue #15:
  [MEDIUM] `_sql_upstreams` regex misses single-char table names
  (`resolver.py:440`); [LOW] dead-code false positive for model-less explores
  (`enrich.py:78`).
- Operator action needed: review and merge PR #14.

```
Commit: a15859e
Conductor Mode: patch
Context Budget: low
Context Loaded: AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/handoff-log.md latest block, src/strata/mcp/tools.py, tests/test_security.py.
Context Skipped: archive/**, handoff-archive.md, slice specs.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no stable tag required.
```
