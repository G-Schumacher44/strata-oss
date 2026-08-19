# Dashboard North Star — product/UX investigation (2026-08-19)

**Provenance:** dispatched product/UX investigation (read-only, grounded in the live
rendered dashboard + raw artifacts at generation time + `dashboard.py`/`enrich.py`),
commissioned after an operator-driven hands-on walkthrough of the published 0.1.8
dashboard. The five concrete walkthrough defects were fixed separately (slice-07); this
document designs ABOVE them.

**Decisions taken on this document (operator, 2026-08-19):** items 4–5 (L1-facts inlining,
evidence sentences, deep links) = **slice-08**; items 1–2, 6–9 (delta, task views,
workbench, blast-radius ranking, by-model rollup, print CSS) = **slice-09**. Non-goals
section is BINDING for future slice authors. Items 10–12 (search, editor links, theming)
remain unscheduled backlog.

---
## What the data actually looks like

- `catalog.json`: 286 nodes — 196 `field`, 34 `explore`, 20 `view`, 19 `model`, 12
  `physical_table`, 5 `pdt`. Rows carry `{id, kind, name, orphan, source_file}` only — no
  description, tag, owner, or team field anywhere in the data model.
- `usage_summary.json`: a single 30-day snapshot — no prior-run fields, no delta, no trend;
  a point-in-time read every time.
- `cleanup_roadmap.json`: 27 actions (14 repair_schema_reference, 11
  review_for_deprecation, 2 review_unused_pdt_cost) — a re-sort of three artifacts sharing
  an `{action, kind, target, evidence_ids}` shape; 25 of 27 have no cost field, so they
  differentiate only by insertion order.
- **Evidence ids reference namespaces (`usage:…`, `pdt_build:…`, `schema_table:…`) that are
  not resolvable client-side**: `build_dashboard_html` embeds only the seven artifacts +
  graph; the raw L1 facts backing the evidence (`explore_usage`, `pdt_builds`,
  `content_references`, built in `enrich.py`) never reach the HTML. Chips can be clickable
  and still have nothing to reveal — the data plumbing is the prerequisite.
- The full-repo graph (71 nodes, ~378 edges) renders on page load as the first thing a
  visitor sees — in a tool whose two real jobs (number-for-the-meeting; safe-delete) don't
  start with topology.
- JS discipline worth preserving: vega/vega-lite (~828KB) live in assets but are
  deliberately NOT embedded in the dashboard — hand-roll small features (search, print,
  clipboard) rather than adding libraries.

## The two jobs

(a) **"Give me the number for the meeting"** — wants KPI row + a "$/mo at risk" headline +
what-changed, done in 15 seconds, never scrolls past a graph.
(b) **"Let me safely delete things"** — wants a workable list with evidence and blast
radius one click away; doesn't care about repo-wide topology.

One fixed scroll forces both jobs through the same path. Task-oriented, hash-addressable
views: **Overview / Cleanup Workbench / Cost / Drift / Graph** (Drift absorbs Migration
Impact — same mismatch from two angles).

## The graph

Full-repo-graph-as-landing is the wrong default at 71 nodes and gets worse at enterprise
scale. Comparable tools agree: dbt docs treats lineage as a neighborhood drill-in from a
selected node (mini-map of immediate parents/children), never a full-DAG landing
(docs.getdbt.com/docs/build/view-documentation); Spectacles' cleanup surface is a ranked
table, graph secondary (spectacles.dev/products/content-management.html); Select Star
navigates by usage/impact score first (selectstar.com/resources/dbt-docs). **Demote the
graph to a drill-in**: any finding row → induced 1–2-hop neighborhood (a subgraph filter on
data already loaded); keep the full graph behind the Graph view as the escape hatch.

## Actionability — list vs workflow

The roadmap is a report, not a workflow: no persisted state, no export, no snippet. Within
the single-file invariant it can still close most of the gap: `localStorage` mark-reviewed
that survives regeneration at the same served path ("triaged 14 of 27"); copy-as-LookML-
snippet (`hidden: yes` + dated STRATA comment) and copy-as-checklist via the Clipboard API;
rank cost-less actions by blast radius (join `migration_impact.json`'s per-table
explore/field counts).

## Trust surfaces

The 30-second convince-a-skeptic experience is a sentence, not a link: *"queried 0 times in
the last 30 days (2026-05-07 → 2026-06-06); 0 content references in the window; exists in
resolved IR at `models/em_legacy_v2.model.lkml`."* Buildable today; requires inlining the
L1 facts as a lookup in the data block. This is the prerequisite that makes clickable
evidence worth clicking.

## The single-file constraint

Rules out: view-time frameworks, web fonts, server state, anything issuing a network
request. Still allows, cheaply: **URL-hash deep links reusing existing artifact ids
verbatim** (~30 lines of JS — ids like `dead:explore:…`/`pdt:…` already exist); localStorage
review-state; hand-rolled search over ~286 entries; `@media print` stylesheet (the
leadership-PDF path — none exists today); Clipboard API.

## Comparative bar

| Tool | The one pattern worth stealing |
|---|---|
| dbt docs | Lineage = neighborhood drill-in from a node, never a full-DAG landing |
| Spectacles | Deprecation as owner-native workflow, not a static list |
| Select Star | Usage/impact score IS the navigation signal |

## Prioritized improvement map

| # | What | Job | Effort | Single-file? |
|---|---|---|---|---|
| 1 | Run-over-run delta (generation-time diff, embedded `DELTA`) | (a) — the weekly-habit lever | M | Yes |
| 2 | Task-oriented views, hash-addressable | (a)+(b) | M | Yes |
| 3 | Graph → drill-in (neighborhood default, full graph behind a button) | (b) | S–M | Yes |
| 4 | Inline raw L1 facts so evidence resolves to sentences | (b) — trust in 30s; prerequisite for clickable evidence | M | Yes |
| 5 | URL-hash deep links on existing ids | (a) — shareable findings | S | Yes |
| 6 | Cleanup Workbench (unify, filter/sort, localStorage review, copy-snippet) | (b) | M–L | Yes |
| 7 | Blast-radius ranking for the 25 cost-less actions | (b) | S | Yes |
| 8 | By-model rollup ("em_legacy_v1/v2 = $63,750/mo, 9 of 11 actions") | (a) | S | Yes |
| 9 | `@media print` stylesheet | (a) | S | Yes |
| 10 | Client-side search / Cmd-K | (b) | S–M | Yes |
| 11 | Editor deep-link from source_file | (b) — blocked on line numbers upstream | S | Yes |
| 12 | Light/dark theme via OS preference | cosmetic | S | Yes |

## North star — two releases from now

You open the dashboard Monday morning at the same URL. Overview: a headline number
("$46.6K/mo at risk, up $1.2K from last week"), a KPI row, a three-line what-changed strip —
no graph, no scroll. In the Cleanup Workbench, last week's fourteen reviewed items are
still checked off; you triage two new zombie PDTs, copy the ready-to-paste `hidden: yes`
snippet for one, and paste a deep link to the other into Slack — it opens straight to that
PDT's evidence. "Show neighborhood" on a flagged explore shows exactly the three views and
one physical table it would take down, not the other 67 nodes. Still one HTML file, zero
external requests, deterministic and token-free — it finally rewards opening it every week.

## Non-goals (BINDING)

- No backend, hosted history, or multi-user state — the delta is a filesystem read at
  generation time.
- No write-back to Looker, no automated PRs — the ceiling is copy-paste-ready snippets;
  read-only is the trust proposition.
- No general content-management surface (org-wide catalogs, owner directories) — that's
  Spectacles'/Select Star's product; Strata's edge is deterministic LookML-repo governance.
- No auth/accounts/sharing infrastructure.
- No WebGL/large-graph performance chase — drill-in makes node-count mostly moot.
- No AI/chat layer in the dashboard — MCP/skills are already the AI surface; "deterministic
  analysis, zero tokens" stays sharp.
