# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-08-18 — fix/dashboard-ux

Commit: 771560e (pre-merge branch anchor; squash-merge repo — post-squash resolve via
  `gh pr view <PR#> --json mergeCommit -q .mergeCommit.oid`)
Anchor semantics (squash-aware, per the convention slice-06 established): PRE-merge,
  771560e is the implementation commit on the PR branch. POST-squash, resolve the
  landed anchor deterministically via `gh pr view <PR#> --json mergeCommit -q
  .mergeCommit.oid` and use THAT for any HEAD check — no branch-SHA ancestry check is
  valid after a squash by construction.
Conductor Mode: slice (governing spec: conductor/slice-07-dashboard-ux.md)
Context Budget: medium
Context Loaded: AGENTS.md, conductor/index.md, conductor/README.md, conductor/templates/CONDUCTOR_SLICE_TEMPLATE.md, handoff-log latest block (slice-06), src/strata/outputs/dashboard.py, src/strata/l1/enrich.py, src/strata/l1/types.py, src/strata/l1/schema.py, src/strata/ir/types.py, src/strata/ir/resolver.py (node/edge id conventions), tests/test_l1_synthesis_outputs.py, output/enterprise_mono/*.json (real fixture artifacts, used to ground the schema-drift dedup investigation).
Context Skipped: handoff-archive.md (not needed beyond the one slice-06 block moved into it), mcp/ and cli/ (out of scope per task), docs/assets screenshots (explicitly deferred to a later pass).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump this slice — pure dashboard-generator fix, no release trigger.

**What changed:** five operator-confirmed UX findings from a hands-on 0.1.8 dashboard
walkthrough, all in `src/strata/outputs/dashboard.py`:

1. **Node detail panel** — PDT/explore/view/physical_table clicks now render every
   fact `_build_graph_data` sources Python-side (cost, build count, bytes scanned,
   dead-marked consumer lists, PDT dependencies, referencing views), replacing the old
   name/kind/source/"DEAD/ORPHAN: Yes" starved panel.
2. **Vocabulary** — a `Status` row replaces the flattened DEAD/ORPHAN flag: PDT →
   ZOMBIE (purple) / UNUSED (orange) / IN USE (green); explore → DEPRECATE/KEEP
   (unchanged); view → ORPHANED (gray) / ZOMBIE VIEW (purple, new third state,
   structurally referenced but every consumer dead) / ACTIVE (blue). Legend extended
   to teach the new zombie-view/in-use-PDT colors.
3. **Evidence links** — `resolveEvidenceNodeId()`/`evidenceHtml()` turn evidence ids
   that name a graph entity into pills that scroll+select+fit+`tap` the graph node
   (`dead:explore:MODEL.NAME` remaps to `explore:MODEL:NAME`); ids with no graph node
   (`usage:`, `pdt_build:`, `schema_table:`, `field:`) render as plain non-pill text.
   Dead Code Register and the new Roadmap `<details>` evidence expansion both route
   through the same helper.
4. **Graph layout** — taller canvas (640px), tuned dagre `rankSep`/`nodeSep`/`padding`,
   `min-zoomed-font-size`, `fit: true` for initial-render fit-with-padding, plus
   overlaid +/−/fit buttons.
5. **Schema Drift dedup** — checked the artifact structure first: rows that look
   byte-identical genuinely differ by `field` (multiple LookML fields referencing the
   same missing column). Surfaced a `Field` column instead of a fake dedup; the JS
   groups on the full row (field included) and only shows a `×N` count if rows are
   truly identical even then.

`src/strata/l1/enrich.py` was read but not changed — every new field is derivable from
data it already produces plus the graph's own edges, computed in one edge pass inside
`_build_graph_data` (the codebase's existing convention of a small local lookup helper
per module, e.g. `validation.py`'s own copy of `_explores_using_view`, rather than
importing a private cross-module function).

**What was verified:**
- Full suite: **112 passed** (109 existing + 3 new tests covering PDT ledger fields on
  both fixture zombies + a negative-control "used" PDT, status vocabulary per kind
  including the new zombie-view/orphan/active three-way split, and the schema-drift
  dedup arithmetic — visible-column grouping collapses fewer rows than raw count,
  full-row-including-field grouping equals raw count).
- `ruff format --check` + `ruff check` clean.
- Self-contained-HTML invariant re-verified against a regenerated enterprise_mono
  dashboard: the only `http(s)://` strings are pre-existing vendored-JS-library doc
  comments (cytoscape/dagre/chart.js), unchanged by this slice.
- Pre-PR gate (`koa review --branch`) run per the mandatory ritual — see PR body for
  the disposition.
- **Not verified**: an actual browser click-through. This dispatch runs headless; the
  `browser-use` MCP tool required an interactive permission grant that isn't available
  here, so it errored on first call. Static review of the JS + the Python-side data
  tests substitute. Flagged explicitly in the PR body as the one item still needing a
  human eyeball before this is fully closed out.

**Review rounds (PR #25):** r1 — inherited consumers (fixture: base_customer under
customer_extended) + ACTIVE badge to legend blue; r2 — the r1 propagation promoted from a
dashboard-local loop into L1 (fix-the-shape applied to the fix itself); r3 — doc alignment;
r4 — the unification split along the REAL seam: `view_consumer_map()` (ancestry-aware
reachability: orphan/zombie-view verdicts + the panel) vs `direct_view_consumers()` (the
PDT ledger — a child view's PDT is its own materialization, so inherited consumers must
never credit a parent's PDT), one shared direct core; r5 — physical-table panel counts
pdt→upstream references, mirroring strata_impact(); r6 — this record corrected to the
final architecture.
mypy caught a str→tuple rebind in CI (venv suites don't run mypy — CI does).

**Exact Next Steps:**
1. Operator (or a session with browser-tool permission) opens the regenerated
   enterprise_mono dashboard.html in a real browser and confirms: node-detail panel
   populates correctly per kind, evidence pills jump to the right graph node, zoom/fit
   buttons work, graph fills the taller canvas legibly, Schema Drift shows the Field
   column with the ×N count only where genuinely duplicated.
2. Twin gate (Artemis/Apollo, this session's pre-PR ritual) + Codex on the PR; merge on
   clean per standing order (dispatched agents never merge).
3. No version bump / tag needed — this is a generator-only fix, not a release artifact
   change. If a future slice wants to regenerate the README dashboard screenshots to
   reflect these UX changes, that's explicitly out of scope here per the task brief.
