# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/dashboard-polish (dashboard redesign: graph legibility + polish)

Commit: (pending — local preview branch, not yet pushed; operator reviews the live preview first)
Conductor Mode: feature — dashboard presentation only; no artifact/schema change.
Context Budget: medium
Context Loaded: AGENTS.md, outputs/AGENTS.md, conductor/dashboard-north-star.md, handoff-log, dashboard.py, cli/dashboard.py, escaping guardrail + dashboard tests.
Exact Next Steps: operator reviews the preview; on approval push and open the PR (twin gate). Open design questions listed in the lane report (light theme, graph-as-landing vs drill-in per the north star, mobile table cards).

### What changed

- Dependency graph: left-to-right layers (explores, views, PDTs/tables) with layer headers; short labels that fade below readable zoom and always show for the hovered/selected neighborhood; per-kind shapes (explore circle, view pill, PDT diamond, table barrel) and a halo on problem nodes; unconnected nodes laid out in their own row; canvas sized to the tallest layer; hover tooltip with the full name; search (name/model), per-kind toggles, a "Needs attention" filter, zoom-to-selection and reset; clickable upstream/downstream lists and a start-here list of problem nodes in the detail panel. Plain wheel scrolls the page; pinch or Cmd/Ctrl-wheel zooms (touch keeps native pinch).
- Single source for status colors: `NODE_PALETTE`/`EDGE_PALETTE` in dashboard.py are stamped onto nodes and emitted as `--n-*`/`--e-*` CSS tokens the legend, badges and PDT chart read. Tests now assert against the palette keys plus a distinctness check.
- New `attention` node flag (Python-side) drives the filter and start-here list. Note: in both fixtures every zombie/unused node is already `orphan`, so the status clause of the flag is belt-and-braces and not independently exercised by fixture data.
- Page polish: sticky section nav, data-driven headline naming the costliest problem, KPI cards ordered by severity and linking to their sections, sentence-case labels, sortable tables with sticky headers inside scroll containers, PDT ledger sorted by cost with palette-coloured chart, responsive to 390px (iframe-verified; headless Chrome cannot size a window below ~500px).
- `strata dashboard` serves dashboard.html at `/` (Host check still runs first; artifacts stay at their paths).

### Gates

ruff check + format --check clean, mypy clean, pytest 213 passed (209 before; +2 root-route host tests, +2 palette/attention tests), dashboard JS `node --check` pass. Negative controls: root-route test fails with the rewrite removed; legend-token test fails with a hand-copied hex; attention test fails with the flag removed.
