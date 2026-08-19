# Slice 07: Dashboard UX fixes — rich node detail, honest zombie vocabulary, live evidence

Date: 2026-08-18
Status: review
Phase: distribution
Depends: slice-06 (mcp 2.x migration, merged 0.1.8)

```yaml
conductor_mode: slice
context_budget: medium
handoff_required: true
stable_tag_required: false
```

## Objective

A hands-on operator walkthrough of the published 0.1.8 dashboard (enterprise_mono
fixtures, real browser) surfaced five UX defects: the flagship node-click panel is
starved, the DEAD/ORPHAN vocabulary flattens the zombie concept the tool exists to
teach, evidence "links" are inert decoration, the dependency graph wastes its canvas,
and the Schema Drift table looks like it's repeating rows. All five live in the same
file (`dashboard.py` is the self-contained HTML generator) — one slice, one PR.

## Scope

`src/strata/outputs/dashboard.py` only (Python `_build_graph_data` + the embedded
CSS/JS template). `src/strata/l1/enrich.py` was read but needed no changes — every new
node-detail field is derivable from data `enrich_graph` already produces (pdt_ledger,
dead_code) plus the graph's own edges; sourcing it in `_build_graph_data` keeps one
edge pass as the single place that computes cross-kind lookups, instead of duplicating
`enrich.py`'s private `_explores_using_view` (the codebase's own convention — see
`validation.py`'s independent copy of the same helper — is a small local copy per
module, not a cross-module import of a private function).

**Scope amendment (review round 2, Codex):** consumer resolution moved OUT of
`dashboard.py` into `src/strata/l1/enrich.py` as `view_consumer_map()` — the ancestry-aware
single source now feeding the dead-code register, the PDT ledger, and the dashboard panel
alike. The original "local edge derivation in the dashboard" wording is superseded: a
dashboard-local derivation could disagree with the register (panel says ZOMBIE VIEW,
register silent), which is exactly the two-sources drift this repo's rules forbid.
`_explores_using_view` remains as the thin per-view API; both enrich call sites hoist the
map once.

## Implementation Order

1. `_build_graph_data`: one edge pass builds `view_explores`, `explore_views`,
   `view_pdt`, `table_views` lookups once.
2. Extend node `data` per kind: PDT (status/cost/build_count/bytes/used_by_explores
   with dead-marking), explore (pdt_dependencies), view (status + referencing_explores
   with dead-marking), physical_table (referencing_views) — computed Python-side, never
   re-derived in JS.
3. View status becomes a real third state: `orphaned` (no explore reference at all,
   from the existing IR `orphan` attr) vs `zombie_view` (referenced, but every consumer
   dead) vs `active` — mirrors the PDT zombie concept instead of collapsing both into
   `orphan`.
4. JS: rewrite the node-detail click handler to render per-kind rows from the new data,
   with a `Status` row (`statusBadge()`) replacing the old flattened `Dead / Orphan: Yes`
   line. Colors match the legend exactly (zombie=purple, unused=orange, in-use=green;
   view zombie also purple, extending the legend to teach it).
5. JS: `resolveEvidenceNodeId()` / `evidenceHtml()` — evidence ids that name a graph
   entity (direct id match, plus the `dead:explore:MODEL.NAME` → `explore:MODEL:NAME`
   remap) become clickable pills that scroll+fit+select+`tap` the graph node; ids with
   no graph node (`usage:`, `pdt_build:`, `schema_table:`, `field:` — fields are excluded
   from the rendered graph) render as plain non-pill text. Dead Code Register pills and
   Roadmap's evidence-link text both route through this one helper.
6. Roadmap "N evidence links" becomes a `<details>` that expands to the real linkified
   ids.
7. Graph layout: taller container (640px), bumped `rankSep`/`nodeSep`/`padding`,
   `min-zoomed-font-size` for legibility, `fit: true` on the dagre layout for
   initial-render fit-with-padding, plus overlaid +/−/fit buttons wired to `cy.zoom()`
   / `cy.animate({fit})`.
8. Schema Drift: checked the artifact structure first (`schema.py` / the enterprise_mono
   fixture) — rows that look byte-identical on kind/table/column/source_file/reason
   genuinely differ by `field` (e.g. three different `legacy_order_detail` fields all
   referencing the same missing `unit_cost_usd` column). Fix surfaces the `Field` column
   instead of deduping; the JS also groups on the *full* row (field included) and only
   collapses with a `×N` count if rows are truly identical even then — handles either
   case honestly rather than hardcoding the one this fixture exercises.
9. New `escapeHtml()` helper used throughout the rewritten node-detail panel and the new
   evidence-link/roadmap code — those are the surfaces this slice touches with
   externally-sourced text reaching `innerHTML`, so they're escaped. Pre-existing
   unescaped interpolation elsewhere in the file (KPI cards, existing table rows) is
   untouched — out of scope for this slice, flagged here rather than silently expanded.

## The Hard Constraint

The dashboard HTML must stay fully self-contained — zero external network requests at
render time. Verified: the only `http(s)://` strings in the generated output are inside
vendored JS library license/doc comments (cytoscape/dagre/chart.js), unchanged by this
slice.

## Acceptance Criteria

- [x] PDT node data carries ledger fields for both fixture zombies
      (`pdt_attribution_full_funnel`, `pdt_customer_value_score`) — cost, build count,
      bytes, dead-marked consumers
- [x] Status vocabulary correct per kind, with a negative control (`pdt_regional_kpi` →
      `used`/green, not zombie/unused)
- [x] Schema drift dedup arithmetic: `visible-column` grouping collapses fewer rows than
      raw count (reproduces the apparent-duplicate complaint), full-row grouping
      (field included) equals raw count (proves no true duplicates were hidden)
- [x] `.venv/bin/pytest` — full suite green (112 passed)
- [x] `ruff format --check` + `ruff check` clean
- [x] Self-contained invariant re-verified against the regenerated enterprise_mono HTML
- [ ] Operator re-walks the dashboard in a real browser to confirm the fixes read right
      (this dispatch is headless — browser-use tool required interactive permission
      grant unavailable here; static/JS review + Python-side data tests substitute)
