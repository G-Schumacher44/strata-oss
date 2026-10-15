# Handoff — fix/load-ir-missing-cache

**Mode:** Patch
**Date:** 2026-10-15

## What changed
- ir/store.py: existence check before sqlite3.connect.
- Regression test in tests/test_mcp_tools.py.

## Verification
Full CI gate set run locally (ruff check, ruff format --check, mypy, pytest, dashboard JS syntax); new regression test fails without the fix.
