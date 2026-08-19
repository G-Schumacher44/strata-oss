# Slice 08: Evidence trust core — L1 facts inlined, evidence sentences, deep links

Date: 2026-08-19
Status: queued
Phase: dashboard
Depends: slice-07 (dashboard UX fixes)

```yaml
conductor_mode: slice
context_budget: medium
handoff_required: true
stable_tag_required: false
```

## Objective

Make a verdict verifiable in under 30 seconds without leaving the page. Today the evidence
ids name facts the page cannot show: the raw L1 facts backing them (`explore_usage`,
`pdt_builds`, `content_references` — built in `enrich.py`) are never embedded in the HTML,
so even clickable chips resolve to nothing for the `usage:`/`pdt_build:` namespaces. This
slice inlines the facts and renders them as plain-language evidence sentences, and adds
URL-hash deep links so any finding is shareable. (Design source:
`conductor/dashboard-north-star.md`, items 4–5.)

## Scope

`src/strata/outputs/dashboard.py` (data assembly + JS), `src/strata/l1/enrich.py` read-only
reuse. No new JS libraries — hand-rolled, per the repo's own vega-exclusion discipline.
Single-file/zero-external-requests invariant is hard.

## Implementation Order

1. **Inline the L1 facts**: extend the data block with an `L1_FACTS` lookup —
   `explore_usage` (per-explore query_count + period), `pdt_builds` (per-view build_count/
   bytes/cost), `content_references` — keyed to match evidence-id namespaces. Python-side,
   one source: the dicts already built in `enrich.py`; never re-derive.
2. **Evidence sentences**: clicking any evidence chip opens an inline panel rendering the
   fact in analyst language — e.g. *"queried 0 times in the last 30 days (2026-05-07 →
   2026-06-06) · 0 content references in the window · exists in resolved IR at
   `models/em_legacy_v2.model.lkml`"*. Graph-node ids keep slice-07's jump-to-node behavior
   AND gain the sentence panel; every namespace now resolves to something honest. All text
   through the existing sanitize path.
3. **URL-hash deep links**: a `hashchange`/load listener resolving existing artifact ids
   verbatim (`#dead:explore:em_legacy_v2.dead_finance_v2`, `#pdt:pdt_attribution_full_funnel`)
   → scroll to the row, open its evidence/detail. Every row gets a copy-link affordance
   (Clipboard API). No new id scheme — the ids already exist.

## The Hard Constraint

Every evidence namespace present in the shipped artifacts must resolve to a rendered
sentence or a named, deliberate fallback — an evidence id that silently no-ops is the
failure mode this slice exists to remove. Enumerate the namespaces from the real artifacts
first; a test pins the enumeration.

## Acceptance Criteria

- [ ] Every evidence-id namespace in enterprise_mono's artifacts resolves (test-pinned)
- [ ] Zombie chip click renders the cost/builds sentence; dead-explore chip renders the
      usage sentence with the real period dates
- [ ] Deep link to both fixture zombies works from a fresh page load (hash → view → row →
      panel), copy-link buttons present
- [ ] HTML remains fully self-contained; suite green; ruff clean
