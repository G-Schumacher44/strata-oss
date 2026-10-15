# Handoff — fix/clean-output-follows-repo

**Mode:** Patch
**Date:** 2026-10-15

## What changed
- cli/main.py: `strata clean` removes `<search_root>/output` instead of cwd-relative `output/`, matching the strata_ir.db sweep (and the __pycache__ sweep in #37). No change when `--repo` is omitted.
- Regression test in tests/test_cli.py.

## Verification
CI gate set run locally; the new test fails without the fix.
