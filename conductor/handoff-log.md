# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-08-18 — feat/dashboard-evidence-trust-core

Commit: f4d3705 (pre-merge branch anchor — implementation commit; squash-merge repo,
  post-squash resolve via `gh pr view 28 --json mergeCommit -q .mergeCommit.oid`)
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
  src/strata/l1/enrich.py, src/strata/l1/schema.py (schema_tables L1 fact + missing_table
  drift's `physical_table:` evidence id), src/strata/l1/types.py,
  src/strata/outputs/artifacts.py (`_cleanup_roadmap()` — evidence_ids[0] convention),
  src/strata/outputs/AGENTS.md (outputs serialize, they do not derive), tests/
  test_l1_synthesis_outputs.py, tests/test_schema_drift.py (missing_table fixture),
  output/enterprise_mono/*.json (real fixture artifacts).
Context Skipped: handoff-archive.md, mcp/ and cli/ (out of scope — no CLI wiring changed),
  docs/assets screenshots (out of scope).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump this slice — pure dashboard-generator addition, no release
  trigger.

### Round 1 — slice-08 initial implementation

1. **L1 facts inlined** — `_build_l1_facts(graph)` extends the data block with a new
   `L1_FACTS` constant: `usage` (per-explore query_count + content-reference count),
   `pdt_build` (build_count/bytes_processed/estimated_cost_usd per PDT view),
   `schema_table` (known column count per table, sourced from `l1.schema_tables`), plus
   the `period` dict.
2. **Evidence sentences** — `evidenceSentence(evId)` JS dispatcher switches on the id's
   namespace and composes an analyst-language sentence per the north star's example
   wording. Clicking ANY evidence chip toggles an inline `.evidence-sentence` panel;
   graph-resolvable chips also fire `focusGraphNode()`.
3. **URL-hash deep links** — Dead Code Register and PDT Ledger rows get stable DOM ids +
   copy-link buttons; `openHashTarget()` scrolls to and opens the target row's panel on
   load/hashchange.

**What was verified:** Full suite green (118 passed), ruff + mypy clean, self-contained
  HTML invariant held. **Browser click-through (Koa head, real Chrome)** caught a
  page-fatal bug the Python suite structurally could not see: the generated `attrEscape`
  helper shipped `/["\]/g` — a non-raw Python string collapsed a backslash layer, so the
  regex character class never closed, killing every script on page load. Fixed by
  eliminating the regex entirely (plain `dataset.evId` string equality). Added the
  pre-push parse guard for this class: extract each `<script>` block and `new Function
  (src)` it in Node.

### Round 2 — Codex round 2 (PR #28, 3 findings) fixed

1. **Output-encoding hardening** — the evidence-sentence panel was built via innerHTML
   over fixture-supplied fields. Fixed by construction: `toggleEvidencePanel` assigns
   `panel.textContent = evId + ': ' + evidenceSentence(evId)` — no HTML parsing of the
   sentence, ever. The now-redundant `escapeHtml(...)` calls inside the sentence-building
   helpers were removed (textContent would have double-escaped, e.g. rendering `&amp;`
   literally).
2. **Every-row copy-link/deep-link** — Schema Drift and Cleanup Roadmap rows had no row id
   or copy-link. `primaryChipHtml()` gained an optional `rowId` param so the DOM-anchor/
   copy-link target can diverge from the chip's evidence-sentence id: Schema Drift uses
   `tr.id = r.id` (the row's own unique `SchemaDriftRecord.id`); Cleanup Roadmap used
   `li.id = r.evidence_ids[0]` at this point (superseded in round 3 — see below).
3. **`schema_table:` sentence names columns, not just a count** — `_build_l1_facts` inlined
   `columns` alongside `column_count`; the JS case rendered names, capped at 30 with a
   `(+K more)` suffix (the cap itself was removed in round 3).

**What was verified:** Full suite green (121 passed — 3 new). ruff + mypy clean.
  **Round-2 browser re-verify (Koa head, real Chrome)** caught a second defect the 121
  Python tests could not: roadmap `li.id = evidence_ids[0]` DUPLICATED PDT Ledger row ids
  for both fixture zombies (invalid document; `getElementById` made the roadmap anchor
  unreachable). Interim fix at the time: claim the id only if not already taken
  (`if (!document.getElementById(primaryId)) li.id = primaryId;`) — the round-3 "defer-if-
  taken" rule, since superseded (see below).

### Round 3 — Codex round 3 (PR #28, 5 findings) fixed — this session

1. **`physical_table:` evidence namespace unhandled** — `missing_table` schema-drift
   records cite the physical table's own graph-node id (`physical_table:<name>`,
   `schema.py`'s `_schema_drift()`) as `evidence_ids[0]`; the Cleanup Roadmap uses
   `evidence_ids[0]` as its primary chip, so this fell through to the generic
   "no evidence sentence defined" fallback. Added a `physical_table` case to
   `evidenceSentence()`: resolves against `L1_FACTS.schema_table` — absent from schema
   facts states so plainly ("...is not present in the provided schema facts (scanned N
   tables)"); present reports column count + `source_file` from the graph node.
   `KNOWN_EVIDENCE_NAMESPACES` extended; the enterprise_mono fixture doesn't itself
   exercise a `missing_table` record, so the new pinned test uses the dedicated
   `tests/fixtures/schema_facts_drift.json` fixture (same one `test_schema_drift.py`
   already relies on for this scenario).
2. **Roadmap rows need row-unique DOM anchors** — replaced round 2's "defer-if-taken"
   rule (which made a claimed roadmap row's anchor silently unreachable) with a dedicated
   `'roadmap:' + primaryId` DOM-fragment namespace, `:2`/`:3`-suffixed on intra-roadmap
   collisions (multiple actions on one target). This is a DOM-anchor namespace only —
   evidence ids on chips stay verbatim (`primaryChipHtml(primaryId, r.target,
   roadmapId)`); `data-copy-hash` is the li's own unique id. `openHashTarget()` needed no
   change (`getElementById` resolves any id; the existing chip-fallback already covers a
   `tr.id`/`data-ev-id` divergence, same pattern as Schema Drift). The round-3-era defer
   rule is now dead code and removed — `roadmap:`-prefixed ids can never collide with a
   ledger/register/drift row's own id by construction.
3. **Dropped the 30-column display cap** in the `schema_table:` sentence — a wide table's
   sentence gets long, which is truthful and acceptable in a text panel; the cap was
   hiding exactly the fact a reader needs (whether the missing column is among the hidden
   ones).
4. **Handoff anchor consolidated** (this file) — the round-1/round-2 anchorless blocks
   folded into this single dated block with one `Commit:` line.
5. **Evidence aggregation moved into L1** — `content_reference_count`-per-explore and the
   schema-table column-count/columns derivation were computed directly in
   `_build_l1_facts()` (an outputs-layer function), violating `outputs/AGENTS.md`'s "outputs
   serialize, they do not derive." Moved into a new `evidence_facts(graph)` function in
   `src/strata/l1/enrich.py` (same seam style as `direct_view_consumers`/
   `view_consumer_map` — plain dict return, no graph mutation); `_build_l1_facts()` now
   only reshapes what that function returns into the evidence-id-keyed shape the JS looks
   up.

**What was verified:**
- Full suite: **124 passed** (121 prior + 3 new: `test_physical_table_evidence_namespace_
  resolves_present_and_missing`, `test_roadmap_and_ledger_dom_ids_are_all_unique`,
  `test_evidence_facts_aggregates_content_refs_and_schema_columns`; two existing tests
  updated in place for the new roadmap-id scheme and the removed column cap).
- `ruff check` + `ruff format --check` clean; `mypy src` clean.
- Regenerated the enterprise_mono fixture dashboard (the CLI's local HTTP server bind
  fails in this sandbox with `PermissionError`, but the HTML write happens first, so the
  regenerated file is current) and ran the pre-push parse guard: extracted all 5
  `<script>` blocks and `new Function(src)`'d each in Node — all 5 parse clean.
- **Behaviorally verified in Node** (same pure-logic-extraction technique as prior
  sessions): `evidenceSentence('physical_table:definitely.not.a.real.table')` →
  *"physical table 'definitely.not.a.real.table' is not present in the provided schema
  facts (scanned 12 tables)."*; a present table reports column count + source_file.
  `schema_table:` sentence now renders the full 8-column list for a real fixture table
  with no truncation. Walked the real generated `ROADMAP` (27 items): all 27 get unique
  `roadmap:`-prefixed DOM ids, zero collisions against `PDT_LEDGER`/`DEAD_CODE`/
  `SCHEMA_DRIFT` row ids.
- Self-contained-HTML invariant re-checked against the regenerated dashboard: only the
  same pre-existing vendored-library license-header URLs, unchanged — zero external
  requests.
- Live-browser click-through of round 3's new sentences/anchors was NOT re-run this
  session (no browser-use permission available here — same gap prior rounds flagged);
  worth a human eyeball on the next browser pass.

**Exact Next Steps:**
1. Push branch; let Codex re-review round 3's fixes.
2. Human/Koa-head browser click-through of the `physical_table:` sentence and the new
   `roadmap:`-anchored deep links (the recurring headless-session gap).
3. Resolve threads only after the head verifies; dispatched agents never resolve threads
   or merge (standing house rule).
4. No version bump / tag needed — generator-only addition, not a release artifact change.
