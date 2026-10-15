# Handoff — fix/navigate-chart-anchor-escape

**Mode:** Patch
**Date:** 2026-10-15

## What changed
- cli/query.py: spec built as dict -> json.dumps; anchor sanitised in the temp filename.
- Regression test in tests/test_cli.py.

## Verification
Full CI gate set run locally (ruff check, ruff format --check, mypy, pytest, dashboard JS syntax); new regression test fails without the fix.
