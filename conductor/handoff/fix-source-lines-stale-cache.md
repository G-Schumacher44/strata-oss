# Handoff — fix/source-lines-stale-cache

**Mode:** Patch
**Date:** 2026-10-15

## What changed
- ir/source_lines.py: _scan_file.cache_clear() at the start of attach_source_lines.
- Regression test in tests/test_mcp_tools.py.

## Verification
Full CI gate set run locally (ruff check, ruff format --check, mypy, pytest, dashboard JS syntax); new regression test fails without the fix.
