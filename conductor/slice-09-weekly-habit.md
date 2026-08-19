# Slice 09: Weekly habit — run-over-run delta, task views, cleanup workbench

Date: 2026-08-19
Status: queued
Phase: dashboard
Depends: slice-08 (evidence trust core)

```yaml
conductor_mode: slice
context_budget: high
handoff_required: true
stable_tag_required: false
```

## Objective

Turn a point-in-time report into the thing an analyst opens every Monday. Three legs
(design source: `conductor/dashboard-north-star.md`, items 1–2, 6–8): memory (what changed
since last run), structure (task-oriented views instead of one fixed scroll), and workflow
(a cleanup workbench you can actually work through).

## Scope

`src/strata/outputs/` (dashboard generator + a new run-snapshot/diff module), CLI wiring
for where snapshots persist. Client side: vanilla JS only. Invariants: single-file HTML,
zero external requests, read-only against Looker/BigQuery, no backend — the diff is a
filesystem read at generation time; browser `localStorage` is the only client state.

## Implementation Order

1. **Run-over-run delta**: at generation, persist a compact snapshot (counts + per-entity
   keys + costs) under the output dir; on next run, diff and embed a static `DELTA` block.
   Overview renders "+N new dead explores · −$X/mo PDT spend · M drift items resolved" with
   entity-level lists behind a fold. First run = honest "no prior run" state, never a fake
   zero-delta.
2. **Task views**: Overview / Cleanup / Cost / Drift / Graph as hash-addressable top-level
   views (slice-08's hash router extends). Overview = KPI row + "$/mo at risk" headline +
   delta strip; **the full-repo graph stops being the landing surface** — Graph view keeps
   it, and every finding row gets "show neighborhood" (induced 1–2-hop subgraph via the
   already-loaded cytoscape). Drift + Migration Impact merge into one Drift view (same
   mismatch, two angles). By-model rollup card on Overview ("em_legacy_v1/v2: $63,750/mo,
   9 of 11 deprecate actions").
3. **Cleanup Workbench**: dead code + roadmap unified, filter/sort; roadmap ranked by
   blast radius (join migration_impact client-side) where cost is absent; `localStorage`
   mark-reviewed surviving regeneration (keyed by stable artifact ids), with a visible
   "triaged N of M"; copy-as-LookML-snippet per action (`hidden: yes` + dated STRATA
   comment) and copy-as-checklist for the meeting.
4. **Print stylesheet** (`@media print`): light background, KPI + tables, graph/chart
   hidden — the leadership-PDF path.

## The Hard Constraint

The delta must be honest about identity: an entity counts as "new" or "resolved" only by
stable id comparison against the prior snapshot — never inferred from count arithmetic
(two appearing while two resolve must show as +2/−2, not 0).

## Acceptance Criteria

- [ ] Two consecutive generations over a mutated fixture produce a correct entity-level
      delta (test builds run A, mutates, builds run B, asserts the diff); first-run state
      honest
- [ ] Hash routes for all five views; graph absent from Overview; neighborhood drill-in
      from a register row shows only the induced subgraph
- [ ] Workbench: reviewed state survives regeneration; snippet copy produces paste-ready
      LookML; blast-radius ranking ordering test-pinned
- [ ] Print CSS renders KPI+tables legibly (spot-check); HTML self-contained; suite green
