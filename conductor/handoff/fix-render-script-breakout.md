# Handoff — fix/render-script-breakout

**Mode:** Patch
**Date:** 2026-10-15

## What changed
- viz/render.py: embedded spec JSON now escapes `<` as \\u003c (same fix as dashboard.py).
- Regression test in tests/test_security.py.

## Verification
Full CI gate set run locally (ruff check, ruff format --check, mypy, pytest, dashboard JS syntax); new regression test fails without the fix.
