# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/s10-chart-columns (chart column validation + --x/--y/--color, spec S10)

Commit: 6808e19
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S10 (D12; finding B6) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the spec (§1, B6, D12, S10), viz/render.py, cli/chart.py, mcp/tools.py, the four chart templates.
Exact Next Steps: twin gate on the PR, operator merges. Other wave-B lanes (S2, S4, S6) land serially; merge `origin/main`, hand-resolve handoff/CHANGELOG and regenerate `docs/reference.md`.

### What changed

- `viz/render.py`: `_check_encoding_columns` runs in `render_chart` (the one seam for `strata chart`, `strata-chart`, MCP `strata_render_chart` and `query navigate --chart`) after empty template channels are stripped. Every `encoding.*.field` must be a key in the union of row keys, else `InvalidInput` naming the missing and the available columns. The check covers single-view charts only: layered, composite (concat/facet/repeat/spec) and transform specs are passed to Vega unchecked, and `aggregate: count` / field `*` channels are skipped. Array channels (tooltip) are walked and Vega field paths (`a.b`, `a[0]`, `a\.b`) are parsed to their first component. Templates with `show_labels` are still checked (the check runs before they are layered). No rows means nothing to compare, so it passes.
- `cli/chart.py`: the four template commands are registered once by `_template_command`; each gains `--x/--y/--color`, which set the channel's field (adding the channel if the template lacks it). Help text lists the required columns and optional channels, read from the template YAML at import.
- README Charts section, CHANGELOG, regenerated `docs/reference.md`.

### Gates

pytest 315 passed (15 in `tests/test_chart_columns.py`), ruff check and format --check clean, mypy `src/strata_lookml` clean. Negative control: with the check replaced by `pass`, the CLI mismatch test and the MCP isError test fail; the override and help tests fail on main because the options do not exist.

