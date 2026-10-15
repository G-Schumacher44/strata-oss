# Handoff — fix/navigate-chart-output-root

**Mode:** Patch
**Date:** 2026-10-15

## What changed
- mcp/tools.py: `chart_output_dir()` is the single source for the guard's canonical root (`~/.strata/output`); the path guard uses it. The guard itself is unchanged.
- cli/query.py: navigate chart writes under `chart_output_dir()` instead of `tempfile.gettempdir()` (`/var/folders` on macOS, rejected by the guard).
- Regression test in tests/test_cli.py (non-/tmp tempdir, HOME redirected).

## Verification
CI gate set run locally; the new test fails without the fix.
