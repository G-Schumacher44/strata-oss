# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/dashboard-polish (dashboard redesign: graph legibility + polish)

Commit: 630bbee
  (Implementation commit; the PR squash-merges. After the merge, resolve the landed anchor with `gh pr view <n> --json mergeCommit`.)
Conductor Mode: feature — dashboard presentation only; no artifact/schema change.
Context Budget: medium
Context Loaded: AGENTS.md, outputs/AGENTS.md, conductor/dashboard-north-star.md, handoff-log, dashboard.py, cli/dashboard.py, escaping guardrail + dashboard tests.
Exact Next Steps: operator approved the preview ("way better"); PR open on the twin gate, operator merges. Follow-ups are listed in the PR body (light theme, graph below the findings, phone card tables, whether the attention filter counts PDTs without build data).

### What changed

- Dependency graph: left-to-right layers (explores, views, PDTs/tables) with layer headers; short labels that fade below readable zoom and always show for the hovered/selected neighborhood; per-kind shapes (explore circle, view pill, PDT diamond, table barrel) and a halo on problem nodes; unconnected nodes laid out in their own row; canvas sized to the tallest layer; hover tooltip with the full name; search (name/model), per-kind toggles, a "Needs attention" filter, zoom-to-selection and reset; clickable upstream/downstream lists and a start-here list of problem nodes in the detail panel. Plain wheel scrolls the page; pinch or Cmd/Ctrl-wheel zooms (touch keeps native pinch).
- Single source for status colors: `NODE_PALETTE`/`EDGE_PALETTE` in dashboard.py are stamped onto nodes and emitted as `--n-*`/`--e-*` CSS tokens the legend, badges and PDT chart read. Tests now assert against the palette keys plus a distinctness check.
- New `attention` node flag (Python-side) drives the filter and start-here list. Note: in both fixtures every zombie/unused node is already `orphan`, so the status clause of the flag is belt-and-braces and not independently exercised by fixture data.
- Page polish: sticky section nav, data-driven headline naming the costliest problem, KPI cards ordered by severity and linking to their sections, sentence-case labels, sortable tables with sticky headers inside scroll containers, PDT ledger sorted by cost with palette-coloured chart, responsive to 390px (iframe-verified; headless Chrome cannot size a window below ~500px).
- Codex P2 on #65: without usage/schema facts the page claimed "This repo is clean." `l1.enrich.analysis_coverage(graph)` (one source, keyed on each enrichment step's own marker: `dead_code` / `schema_drift`) is embedded as `COVERAGE`; the headline, KPIs and empty states read it and say "not run" instead of clean/0. Headline/KPI wording lives in pure JS functions (`heroCopy`, `kpiCards`) that the test runs in node against real artifacts.
- `strata dashboard` serves dashboard.html at `/` (Host check still runs first; artifacts stay at their paths).

### Gates

ruff check + format --check clean, mypy clean, pytest 215 passed (209 before; +2 root-route host tests, +2 palette/attention tests, +2 coverage/not-run tests), dashboard JS `node --check` pass. Negative controls: not-run test fails with the clean-headline gate removed, with KPI coverage forced on, and against the pre-fix dashboard; root-route test fails with the rewrite removed; legend-token test fails with a hand-copied hex; attention test fails with the flag removed.
