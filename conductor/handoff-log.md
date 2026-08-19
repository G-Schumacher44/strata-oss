# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-08-18 — feat/dashboard-evidence-trust-core

Commit: (set on final commit — pre-merge branch anchor; squash-merge repo — post-squash
  resolve via `gh pr view <PR#> --json mergeCommit -q .mergeCommit.oid`)
Anchor semantics (squash-aware, per the convention slice-06 established): PRE-merge, the
  final commit on the PR branch is the implementation anchor. POST-squash, resolve the
  landed anchor deterministically via `gh pr view <PR#> --json mergeCommit -q
  .mergeCommit.oid` and use THAT for any HEAD check — no branch-SHA ancestry check is
  valid after a squash by construction.
Conductor Mode: slice (governing spec: conductor/slice-08-evidence-trust-core.md)
Context Budget: medium
Context Loaded: AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/index.md,
  conductor/README.md, active slice conductor/slice-08-evidence-trust-core.md,
  conductor/dashboard-north-star.md, conductor/slice-07-dashboard-ux.md (consumer-map
  split amendment), handoff-log latest block (slice-07), src/strata/outputs/dashboard.py,
  src/strata/l1/enrich.py (read-only reuse), src/strata/l1/schema.py (schema_tables L1
  fact — not named in the slice text but already built Python-side, same class of raw L1
  fact as explore_usage/pdt_builds), src/strata/l1/types.py, src/strata/outputs/artifacts.py,
  src/strata/synthesis/AGENTS.md (evidence-id catalog), tests/test_l1_synthesis_outputs.py,
  output/enterprise_mono/*.json (real fixture artifacts — enumerated evidence namespaces
  from these directly rather than guessing).
Context Skipped: handoff-archive.md (not needed beyond the slice-07 block moved into it),
  mcp/ and cli/ (out of scope — no CLI wiring changed), docs/assets screenshots (out of
  scope, not requested).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump this slice — pure dashboard-generator addition, no release
  trigger.

**What changed** (`src/strata/outputs/dashboard.py` only, per the slice's scope):

1. **L1 facts inlined** — `_build_l1_facts(graph)` extends the data block with a new
   `L1_FACTS` constant: `usage` (per-explore query_count + content-reference count,
   content refs counted Python-side from `l1.content_references`), `pdt_build`
   (build_count/bytes_processed/estimated_cost_usd per PDT view), `schema_table` (known
   column count per table, sourced from `l1.schema_tables` — already built by
   `enrich_schema_drift` in `schema.py`, just never embedded before), plus the `period`
   dict. Every number is read once from `graph.metadata["l1"]`, never re-derived in JS.
2. **Evidence sentences** — a new `evidenceSentence(evId)` JS dispatcher switches on the
   id's namespace (the substring before the first `:`) and composes an analyst-language
   sentence per the north star's example wording. Graph-node namespaces (`explore`,
   `view`, `pdt`, `dead`) compose from the node's own `GRAPH_DATA` fields (already
   Python-sourced) plus `L1_FACTS.usage` for the period/content-reference clause;
   non-graph namespaces (`usage`, `pdt_build`, `schema_table`, `field`) compose from
   `L1_FACTS` directly with an honest fallback when no fact was provided (e.g. "no usage
   row was provided... in the L1 facts", "table ... was not found in the provided schema
   facts"). `field:` ids get a named deliberate fallback (no field-granularity L1 fact
   exists) rather than a silent no-op. `resolveEvidenceNodeId()` gained a `dead:view:`
   remap (slice-07 only had `dead:explore:`) so zombie-view rows also jump-to-node.
   Clicking ANY evidence chip (pill-link or plain) now toggles an inline
   `.evidence-sentence` panel next to the chip via a unified `.ev-chip` click handler;
   graph-resolvable chips ALSO still fire `focusGraphNode()` (slice-07 behavior kept, per
   the slice's explicit "keep AND gain" instruction).
3. **URL-hash deep links** — Dead Code Register rows get `tr.id = r.id` (e.g.
   `dead:explore:em_legacy_v2.dead_finance_v2`) and PDT Ledger rows get
   `tr.id = 'pdt:' + r.view`; each row's Name/View cell is rendered via a new
   `primaryChipHtml()` helper — the row's own artifact id as a chip (evidence-sentence +
   graph-jump if resolvable) plus a 🔗 copy-link button (Clipboard API, verbatim id in the
   hash — colons/dots are legal unencoded fragment characters per RFC 3986, so no
   encode/decode mismatch with the ids' own literal form). `openHashTarget()` runs on
   `load` and `hashchange`: reads `location.hash`, looks up the row by
   `document.getElementById` (exact string match, no CSS-selector escaping needed),
   scrolls it into view, and opens its primary chip's sentence panel.

`src/strata/l1/enrich.py` and `src/strata/l1/schema.py` were read but not changed — every
new fact is a value they already compute (`explore_usage`, `pdt_builds`,
`content_references`, `schema_tables`), just not previously embedded in the HTML.

**Design decisions not fully spelled out in the slice text:**
- The slice named `explore_usage`/`pdt_builds`/`content_references` as the facts to
  inline; `schema_tables` (built in `schema.py`, not `enrich.py`) was added too because
  the hard constraint requires the `schema_table:` namespace (present in the real
  enterprise_mono artifacts — verified by walking the actual JSON, not assumed) to
  resolve to a real sentence, not just a bare fallback.
- A toggle-anchor bug was caught during self-review: `primaryChipHtml()` puts a
  copy-link `<button>` immediately after the chip `<a>`, so the original
  `chip.nextElementSibling` toggle-check would always miss the previously-inserted
  panel (button, not panel, is the immediate sibling) and stack duplicate panels on
  repeated clicks. Fixed by anchoring the panel after the copy-link button when one is
  present, the chip otherwise.

**What was verified:**
- Full suite: **118 passed** (112 existing + 2 new data-correctness/namespace-pin tests
  in `tests/test_l1_synthesis_outputs.py`, matching the existing file's convention of
  testing Python-side data and HTML string-presence rather than DOM behavior).
- `test_evidence_namespaces_all_have_sentence_handling` walks the REAL enterprise_mono
  artifacts (`dead_code_register`, `pdt_ledger`, `cleanup_roadmap`, `schema_drift`),
  enumerates every `evidence_ids` namespace it finds (8: `dead`, `explore`, `view`,
  `pdt`, `field`, `usage`, `pdt_build`, `schema_table`), asserts that set is a subset of
  `dashboard.py`'s new `KNOWN_EVIDENCE_NAMESPACES` constant, and greps the generated HTML
  for a literal `case '<namespace>'` per namespace — this is the hard-constraint pin: a
  namespace absent from the constant OR missing its JS case fails the test.
- `ruff format --check` + `ruff check` clean; `mypy src/strata --ignore-missing-imports`
  clean.
- Self-contained-HTML invariant re-verified against a regenerated enterprise_mono
  dashboard: only pre-existing vendored-JS-library doc-comment URLs, unchanged.
- **JS logic behaviorally verified with Node** (this session has Node locally; CI's
  pytest job does not, so no test depends on it — this was manual pre-push verification
  only, not a checked-in test): extracted the generated `<script>` block's pure-logic
  portion (data constants through `evidenceSentence`), stubbed `document` minimally, and
  called `evidenceSentence()` directly against the real generated `L1_FACTS`/`GRAPH_DATA`
  for both fixture zombies. Output for `dead:explore:em_legacy_v2.dead_finance_v2`:
  *"queried 0 times in the last 30-day window (2026-05-07 → 2026-06-06) · 0 content
  references in the window · exists in resolved IR at 'models/em_legacy_v2.model.lkml'."*
  — matches the north star's example sentence almost verbatim. Also verified: the zombie
  PDT cost/build sentence, the schema_table present/missing fallback, the field:
  fallback, `resolveEvidenceNodeId()` correctly returns `null` for the four non-graph
  namespaces (preserving slice-07's pill/plain boundary), and the hash id round-trip
  (`decodeURIComponent` is a no-op on unencoded colons/dots, and also correctly reverses
  `encodeURIComponent` for a defensively-percent-encoded paste).
- **Not verified**: an actual browser click-through (chip click → panel appears in the
  DOM at the right position; hash-on-load scroll-and-open). This dispatch runs headless
  with no `browser-use` permission available — same gap slice-07 flagged. The Node-level
  logic verification above substitutes for the pure-function correctness; DOM
  wiring/visual layout is the one item still needing a human eyeball.

**Exact Next Steps:**
1. Operator (or a session with browser-tool permission) opens the regenerated
   enterprise_mono dashboard.html in a real browser and confirms: clicking a dead-explore
   chip and a zombie-PDT chip opens the sentence panel in the right place; pasting
   `#dead:explore:em_legacy_v2.dead_finance_v2` or `#pdt:pdt_attribution_full_funnel`
   into the URL on a fresh load scrolls to and opens that row; copy-link buttons put a
   working URL on the clipboard.
2. Twin gate (Artemis/Apollo, this session's pre-PR ritual) + Codex on the PR; merge on
   clean per standing order (dispatched agents never merge).
3. No version bump / tag needed — generator-only addition, not a release artifact
   change.
