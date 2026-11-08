# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — fix/chart-output-path (chart output: no fixed /tmp path, no symlink following)

Commit: 4afba41 (initial fix; review-round fixes follow it. The PR squash-merges; post-merge resolve
  the landed anchor with `gh pr view 61 --json mergeCommit`.)
Conductor Mode: patch — security hardening, no new tool or layer change.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, viz/render.py, cli/chart.py, mcp/tools.py, l1/looker.py
  (the #58 O_NOFOLLOW pattern), docs/security-hardening.md.
Exact Next Steps: operator merges after twins/Codex pass; CHANGELOG Unreleased > Security rides the
  next tag.

### What changed

- `render_chart(out_path=None)` defaults to a fresh `mkstemp("strata_chart_*.html")`; explicit
  paths are opened with `O_NOFOLLOW` (`_write_html`). Where `O_NOFOLLOW` is absent, an lstat
  (`is_symlink`) check refuses a symlink instead.
- `strata chart` / `strata-chart` `--out` no longer defaults to `/tmp/strata_chart.html`.
- MCP `strata_render_chart` resolves only the parent dir and refuses a final-component symlink
  before the root check, so confinement does not depend on `O_NOFOLLOW`.
- `strata query navigate --chart` goes through `strata_render_chart`, so it is covered.

### Verification

- New tests in `tests/test_security.py` (fresh default, normal write, symlink refused in
  render_chart + MCP, symlink refused with `O_NOFOLLOW` monkeypatched away). Reverting `src/`
  makes the behavior tests fail; restored, all pass.
- Full suite 186 passed (with test submodules initialised), ruff, ruff format, mypy clean.
