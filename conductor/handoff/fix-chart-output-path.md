# Handoff: fix/chart-output-path

## Commit anchor
Base: origin/main 4b21b84 (#58). Branch: fix/chart-output-path.

## Change
- `viz/render.py`: `render_chart(out_path=None)` defaults to a fresh `tempfile.mkstemp("strata_chart_*.html")`; explicit paths are opened with `O_NOFOLLOW` (`_write_html`) and a symlink at the final component raises `ValueError`. `strata-chart --out` default is now unset.
- `cli/chart.py`: all `--out` defaults (was fixed `/tmp/strata_chart.html`) are unset; help text updated.
- `mcp/tools.py`: `strata_render_chart` resolves only the parent directory, so a final-component symlink is no longer followed by `.resolve()` before the check.
- Docs/CHANGELOG (Unreleased -> Security), chart_composer SKILL.md, docs/security-hardening.md updated.
- `strata query navigate --chart` writes through `strata_render_chart`, so it is covered.

## Verification
- New tests in `tests/test_security.py` (default path fresh, explicit write, symlink refused in render_chart and MCP). With `src/` reverted, 3 of the 4 behavior tests fail; restored, all pass.
- Full suite: 1 pre-existing failure, `test_pdt_ledger_unused_status_unaffected_by_zombie_detection`, which also fails on unmodified origin/main. ruff, ruff format, mypy clean.
