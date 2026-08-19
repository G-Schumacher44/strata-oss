# Slice 08: Evidence trust core — L1 facts inlined, evidence sentences, deep links

Date: 2026-08-19
Status: review
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

**As implemented (reconciled 2026-08-19 after review — the original scope is preserved below
because the expansion was review-driven, not drift).**

- `src/strata/outputs/dashboard.py` — data assembly + JS (as planned).
- `src/strata/l1/enrich.py` — **WRITE, not read-only reuse.** Review round 3 established that
  aggregation belongs in L1 per `outputs/AGENTS.md` (outputs serialize, they do not derive);
  round 7 caught a later inline fix re-deriving in the outputs layer and moved it back. The
  slice now owns `evidence_facts()` and the `explore_usage_evidence` backfill.
- `src/strata/l1/provider.py`, `src/strata/l1/looker.py`, `src/strata/pipeline.py` — the live
  Looker usage window. Review found `--days N` was dropped before reaching L1, so every live
  evidence sentence would have claimed an unknown window while the provider had queried a
  known range. Plumbing the real period through was the only honest fix; a sentence that
  states its own scope is the point of the slice.

Unchanged hard constraints: no new JS libraries (hand-rolled, per the repo's vega-exclusion
discipline); single-file / zero-external-requests.

*Original scope, for the record:* `dashboard.py` plus read-only reuse of `enrich.py`.

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
   (Clipboard API).

   **Amended after review:** "no new id scheme" held for *evidence* ids and still does — every
   chip carries the artifact's own pre-existing evidence id, verbatim. It did NOT survive for
   *DOM anchors*, and deliberately so: Cleanup Roadmap items own no artifact id, and two
   distinct schema-drift rows can share one `SchemaDriftRecord` id, so reusing data-derived
   keys as element ids produced duplicate DOM ids whose copy-links silently resolved to the
   wrong row (found twice, rounds 3 and 12). The implementation therefore adds a DOM-anchor
   namespace separate from the evidence-id namespace: roadmap anchors are prefixed `roadmap:`,
   and every data-derived anchor routes through one shared `uniqueAnchor()` helper that keeps
   the first occurrence bare (already-shared links stay valid) and suffixes later collisions.
   Anchors are also URL-encoded on write, since the reader decodes.

## The Hard Constraint

Every evidence namespace present in the shipped artifacts must resolve to a rendered
sentence or a named, deliberate fallback — an evidence id that silently no-ops is the
failure mode this slice exists to remove. Enumerate the namespaces from the real artifacts
first; a test pins the enumeration.

## Acceptance Criteria

- [x] Every evidence-id namespace in enterprise_mono's artifacts resolves (test-pinned)
- [x] Zombie chip click renders the cost/builds sentence; dead-explore chip renders the
      usage sentence with the real period dates
- [x] Deep link to both fixture zombies works from a fresh page load (hash → view → row →
      panel), copy-link buttons present — implemented + logic verified with Node against
      the real generated data block (see handoff); an actual browser click-through is the
      one item still needing a human eyeball (this dispatch is headless, same gap slice-07
      flagged — no browser-use permission available here)
- [x] HTML remains fully self-contained; suite green; ruff clean
