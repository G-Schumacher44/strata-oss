# Handoff — fix/navigate-two-part-table

**Mode:** Patch
**Date:** 2026-10-15

## What changed
- navigate.py: _classify_anchor consults the graph for two-part anchors.
- Regression test in tests/test_mcp_tools.py.

## Verification
Full CI gate set run locally (ruff check, ruff format --check, mypy, pytest, dashboard JS syntax); new regression test fails without the fix.
