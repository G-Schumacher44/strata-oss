# Handoff — fix/latest-iso-compare

**Mode:** Patch
**Date:** 2026-10-15

## What changed
- l1/replay.py: parsed-instant comparison; l1/looker.py imports it (duplicate removed).
- Regression test in tests/test_l1_providers.py.

## Verification
Full CI gate set run locally (ruff check, ruff format --check, mypy, pytest, dashboard JS syntax); new regression test fails without the fix.
