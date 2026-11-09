# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/wb-s7-overview (Overview as a written report; workbench S7)

Commit: 49ce93c
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S7 of `workbench-spec-2026-11-08.md` (D1 inline SVG, D2 Overview reads, §4 Overview wireframe).
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D1, D2, §4, §5 S7), the approved mockup + shot-overview.png, workbench/{app,render,index}.py + templates, mcp/tools.py (usage/pdt/drift), outputs/artifacts.py, l1/enrich.py, links.py.
Exact Next Steps: twin gate, operator merges. S10 deletes the old dashboard (and its Chart.js); S11/S6 consume the same `links.py` paths.

### What changed

- `workbench/overview.py`: `overview_context(wb)` lifts numbers and rows from `strata_ir_status`, `strata_usage_summary`, `strata_pdt_costs`, `strata_schema_drift`, `cleanup_roadmap` and the findings index; it formats and links (`links.object_path`), nothing else. Each section's `ran` flag is `analysis_coverage`.
- `templates/overview.html`: the fixed sentence templates. A section whose check did not run says "Not run — load <X> facts" in place of any number (headline findings read "findings not run" when neither check ran and none exist; never "0"). Content facts missing: the dead sentence says "no queries" only and names the missing facts. PDT build facts missing: "Not run — load PDT build facts".
- Window label comes from `period.days`: "30 days" only when the facts say 30; another length prints as is; no period prints "length not recorded". Never "/mo" (the label half of spec N8).
- `workbench/charts.py`: `bar(value, total, width, height)` emits SVG with numeric attributes and fixed literals only (no text, no label; bools, NaN, inf, strings raise). The page passes it through `render.safe_svg`, still the only `Markup` site. Colour is CSS on the section.
- `outputs/artifacts.py`: `_cleanup_roadmap` is now public `cleanup_roadmap` (spec D2); one caller updated.
- `app._overview` renders `overview.html`; the placeholder facts are gone. No Chart.js in the workbench; the old dashboard is untouched (S10).
- `tests/test_workbench_server.py`: the hostile-fixture tag/attribute allowlist grew by the report's structural tags (table, strong, svg, rect, span, ...) and numeric SVG attributes; `img`/`script`/`on*` remain forbidden.

### Deviations from the brief

- The top-explores share ("top N carry X%") is the ratio of two tool numbers (the listed rows' query counts over `total_queries`); the rows come from `l1.explore_usage`, which no tool lists per explore. Only explores with queries are listed.
- Next-actions links go to the object page of each item (`evidence_ids[0]`); finding-page links wait for S6 and the findings list (S5).

### Gates

pytest 605 passed, 1 skipped; ruff check + format --check clean; mypy clean; `gen_reference.py --check` clean. Fail-before: `tests/test_workbench_overview.py` against origin/main (detached worktree) errors at collection (no `workbench.overview`). Negative control: forcing the usage section's `ran` to True fails `test_not_run_without_facts_never_zero` and `test_mutation_flipping_coverage_changes_the_sentence`; reverted, 8 pass. Screenshots: /Volumes/t9/dev/dev_project_tmp/wb-s7/{full,notrun}.png.
