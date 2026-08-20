# Handoff Archive

Older handoff blocks moved out of the thin active log (`handoff-log.md` keeps the current block only — conductor/AGENTS.md).

## 2026-08-18 — feat/dashboard-evidence-trust-core

Commit: 5cc13b9 (pre-merge branch anchor — implementation commit; squash-merge repo,
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

### Round 4 — Codex round 4 (PR #28, 2 findings) fixed — this session

1. **Live usage window dropped on the provider path** — `strata dashboard --looker-url
   --days N` passes `days` to `LookerSystemActivityProvider`, but `UsageFacts.to_mapping()`
   never carried a `period`, so `build_graph_with_provider()` called `enrich_graph()` with
   none and the serialized L1 `period` was `{}` — live evidence sentences would have
   claimed an unknown window despite the provider querying a known N-day range. Added an
   optional `period()` hook: NOT part of the `UsageProvider` Protocol (fixture/replay
   providers don't know their own window and must stay conformant without it), duck-typed
   via `getattr(provider, "period", None)` in `UsageFacts.from_provider()`. Added
   `LookerSystemActivityProvider.period()` returning the same `{start, end, days}` shape
   the fixture path already uses (`l1/fixtures.py`'s `load_usage_facts()`) — `end` is
   `datetime.now(UTC)`, `start` is `end - timedelta(days=self.days)`, mirroring the
   `f"{self.days} days"` relative-to-now filter `run_inline_query()` already sends.
   Threaded `period=mapping.get("period")` through `build_graph_with_provider()` in
   `pipeline.py`. No new period schema — one shape, matching the existing L1 convention
   exactly.
2. **PDT evidence sentence claimed a fabricated `/mo` figure** — `pdt_builds()` filters to
   `self.days` and sums bytes with zero monthly normalization, but `pdtCostSentence()`
   (this PR's own new wording) said `$X/mo`. Per operator disposition: do NOT extrapolate
   to a synthetic monthly number (that fabricates a different figure than what was
   measured) — state the cost over its real window instead, reusing `periodPhrase()`
   (same function `exploreUsageSentence()` already uses, including its honest "an unknown
   window" fallback when period is absent). New wording: `"$X estimated over the last
   N-day window (start → end)"` (or `"...over an unknown window"` with no period). Only
   this PR's own new sentence changed — pre-existing `/mo` UI surfaces (PDT Ledger table's
   COST/MO column, roadmap savings line, node detail panel's "Cost / mo" row) are
   untouched; explicitly out of scope per disposition. **Follow-up candidate, not fixed
   here:** those pre-existing `/mo` surfaces may now read as inconsistent next to the new
   window-labeled evidence sentence — worth a human call on whether to unify their wording
   in a future slice.

**What was verified:**
- Full suite: **126 passed** (124 prior + 2 new: `test_looker_provider_period_
  propagates_actual_query_window` — pins a non-30 `days=45` value so a hardcoded default
  couldn't fake it passing, asserts `(end - start).days == days`; `test_pdt_cost_
  sentence_states_real_window_not_fabricated_monthly` — asserts the fixed source line is
  present and the old `/mo)` line is gone).
- `ruff check` + `ruff format --check` clean; `mypy src` clean.
- Regenerated the enterprise_mono fixture dashboard (same sandbox `PermissionError` on
  the HTTP server bind as round 3 — HTML write happens first, mtime confirmed current)
  and ran the pre-push parse guard: extracted all 5 `<script>` blocks and
  `new Function(src)`'d each in Node — all 5 parse clean.
- **Behaviorally verified in Node** (same pure-logic-extraction technique as prior
  rounds): extracted `periodPhrase()` + `pdtCostSentence()` from the regenerated HTML and
  ran them against a synthetic 45-day period → `"built 3 times, processing 500000B ·
  $12.34 estimated over the last 45-day window (2026-01-01 → 2026-02-15) · used by 2
  explores (1 dead) · exists in resolved IR at 'models/foo.view.lkml'."`; against an empty
  period → `"...estimated over an unknown window..."` (no fabricated number, no crash).
- Self-contained-HTML invariant re-checked against the regenerated dashboard: only the
  same pre-existing vendored-library license-header URLs, unchanged — zero external
  requests.
- Live-browser click-through was NOT re-run this session (no browser-use permission
  available here — same recurring headless-session gap prior rounds flagged).

- **Round 5 (Koa head, inline, commit cd109fc)** — Codex caught that a live never-queried
  explore emits NO System Activity row, so the usage-keyed comprehension dropped exactly
  the explores whose dead verdicts most need evidence (chips fell to the "no usage row"
  fallback, substantiating neither verdict condition). `_build_l1_facts` now backfills
  every explore node with a `no_usage_row: true` zero-usage entry (content-ref count
  retained); the sentence states the absence as the zero-usage fact. Pinned by
  `test_l1_facts_covers_explores_without_usage_rows` (127 total). Done inline: a bounded
  single-file fix mid-verification, cheaper than a fifth dispatch round-trip.

- **Round 6 (Koa head, inline, commit fc6936c)** — Codex: `json.dumps` leaves `<` intact, so
  a fixture value containing `</script>` would terminate the inline script element and
  hand the rest of the payload to the HTML parser as live markup (reaches the page via
  the raw `L1_FACTS` literal, upstream of the textContent panel hardening). Fix:
  `_embed_json` wraps every one of the 9 JSON embed sites, encoding `<` as `\u003c` —
  byte-identical after JS string parsing, a pure serialization change. Pinned by
  `test_embedded_json_cannot_break_out_of_script_block` (poisons `period.start` with a
  breakout payload and asserts no script block carries it raw; 128 total).

- **Round 7 (Koa head, inline, commit f94e811)** — Codex (P1, correctly): the r5 backfill
  lived in `_build_l1_facts()`, re-deriving facts in the outputs layer — the exact drift
  the `evidence_facts()` seam exists to prevent, reintroduced by my own inline fix. The
  per-explore usage evidence (row-backed and `no_usage_row` backfill alike) now comes
  entirely from `l1.enrich.evidence_facts()` as `explore_usage_evidence`; the dashboard
  reshape is verbatim (test-pinned at both the seam and the reshape; 128 total).

- **Round 8 (Koa head, commit 071fdf1)** — Apollo blocker, correct: CI runs BOTH `ruff check`
  and `ruff format --check`; my r5/r6 inline rounds only ran the former, so two files
  landed unformatted. Formatting applied; the full gate set (check + format --check +
  pytest 128 + mypy) is now green together. Lesson recorded here rather than as a new
  memory shape: run the gate set CI runs, not the subset you remember.
  (Artemis's companion finding — PDT window wording "still unaddressed" — is stale: the
  wording landed in 3987015 and reads `estimated over ${periodPhrase()}` at
  dashboard.py:626. Disputed with evidence on the PR, not silently ignored.)

- **Round 9 (Koa head, commit f8fa376)** — Codex: prototype-chain lookups. A table named
  `constructor`/`toString` resolved to an inherited Object.prototype member, so a MISSING
  table rendered as present with an undefined column count — evidence contradicting its own
  verdict. Fixed as a CLASS: Codex named two sites; all four L1 fact lookups now route
  through `ownFact()`, and `NODE_BY_ID` uses `Object.create(null)` so a `__proto__` key
  can't poison it on assignment either. Regression test asserts no raw bracket lookup into
  a JSON-parsed fact map survives (129 tests). Full gate set run this time — check, format,
  pytest, mypy, Node parse — per the r8 lesson.

- **Round 11 (Koa head, commit 05ccac8)** — Codex: copy-link/hash asymmetry. The writer emitted
  the raw row id; the reader applied `decodeURIComponent`, so an id containing a literal
  percent-escape (quoted physical table `foo%20bar`) decoded to `foo bar` and matched
  nothing. Writer now encodes; reader decodes then falls back to the raw hash so links
  copied from an earlier build still resolve. Regression test pins both directions (130).
  NOTE: the post-reboot scratchpad venv was gone, so the first gate attempt silently ran
  against a STALE generated artifact — rebuilt the venv and re-ran everything against the
  real regenerated file. Same greens-by-construction shape as r8, different instrument.

- **Round 12 (Koa head, commit 7f49274)** — Codex: duplicate DOM ids on schema-drift rows (two
  views in different files can share one SchemaDriftRecord id). SECOND appearance of this
  class after r3's roadmap collision, so fixed as one shared `uniqueAnchor()` helper both
  row classes route through, rather than a third bespoke rule; roadmap's private counter
  deleted. First occurrence keeps the bare id so already-shared links stay valid. Also
  rewrote the drift/roadmap id test: it pinned literal source lines, so a correct refactor
  failed it while the property still held — it now asserts the property (131 tests).

- **Round 13 (Koa head, commit 54d01ad)** — Codex P1: the governing slice document had gone stale
  against twelve rounds of review-driven scope change (still said dashboard.py-only + read-only
  `enrich.py`, still prohibited any new id scheme). Reconciled: the L1 write, the
  provider/looker/pipeline reach for the live usage window, and the DOM-anchor namespace are
  now stated as implemented, with the ORIGINAL text preserved alongside — the expansions were
  review-driven, not drift, and a future session should be able to see which is which. Evidence
  ids remain verbatim; only DOM anchors got a namespace.

- **Round 14 (Koa head, commit 5cc13b9) — found by internal sweep, not review.** Escaping was
  applied per-FIELD rather than per-SOURCE: `source_file` was escaped in the Schema Drift row
  and raw in the Dead Code Register row three functions away, plus `kind`, `static_reason`,
  `usage_reason`, `physical_table`, and the KPI card's label/value/sub. Now uniform — every
  record field routes through `escapeHtml()`, numerics included, because exempting them by
  name rebuilds the enumerate-the-bad-cases shape. Test asserts the property structurally, not
  a field list; mutation-verified, and it caught two sites the sweep itself missed (132 tests).

**Exact Next Steps:**
1. Push branch; let Codex re-review round 4's fixes.
2. Human/Koa-head browser click-through of the new PDT cost-sentence window wording (the
   recurring headless-session gap).
3. Consider (follow-up slice, not this PR): unify the pre-existing `/mo`-labeled UI
   surfaces (PDT Ledger COST/MO column, roadmap savings, node detail panel) with the new
   window-labeled evidence-sentence wording, now that both coexist on the page.
4. Resolve threads only after the head verifies; dispatched agents never resolve threads
   or merge (standing house rule).
5. No version bump / tag needed — generator-only addition, not a release artifact change.

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

## 2026-08-17 — feat/mcp-2x-migration

Commit: 1740642 (pre-merge branch anchor; squash-merge repo — post-squash resolve via
  `gh pr view <PR#> --json mergeCommit -q .mergeCommit.oid`)
Anchor semantics (squash-aware — this repo squash-merges, so branch SHAs never survive
  the merge): PRE-merge, 1740642 is the implementation commit on the PR branch. POST-squash,
  resolve the landed anchor deterministically via
  `gh pr view 22 --json mergeCommit -q .mergeCommit.oid` and use THAT for any HEAD check —
  no branch-SHA ancestry check is valid after a squash by construction. Canonical convention
  decision tracked in the repo issue "handoff anchors vs squash-merge".
Conductor Mode: slice (governing spec: conductor/slice-06-mcp-2x-migration.md)
Context Budget: low
Context Loaded: AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/index.md, handoff-log latest block, src/strata/mcp/server.py, tests/test_mcp_server.py.
Context Skipped: handoff-archive.md, docs/ (untouched).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: v0.1.8 tag is the post-merge publish trigger (operator/Koa on instruction).

**What changed:** migrated off the removed 1.x `mcp.server.fastmcp` API to mcp 2.x
(`mcp.server.mcpserver.MCPServer`), closing the follow-up named in the 0.1.7 handoff.

- `src/strata/mcp/server.py`: `FastMCP("strata")` + the `_mcp_server.version` workaround →
  `MCPServer("strata", version=_server_version())` — 2.x takes version as a first-class
  kwarg, so the #20 workaround retires cleanly. `@server.tool()` and `run(transport="stdio")`
  are API-compatible; no tool code changed.
- `pyproject.toml`: `mcp>=2,<3`. The upper bound STAYS as policy — an unbounded pin is what
  shipped a dead-on-arrival strata-mcp once (PR #18); lift `<3` only with a 3.x migration.
- `tests/test_mcp_server.py`: asserts the public `server.version` (2.x) instead of the 1.x
  private `_mcp_server.version`.
- Version triple-bumped 0.1.8 (pyproject, mcpb/manifest.json, mcpb shim pin) — tag guard
  verified consistent at 0.1.8.

**What was verified (fresh venv on mcp 2.x, resolver picked 2.0.0):**
- Full suite **108 passed**; ruff format+check clean.
- Live stdio handshake: `serverInfo {'name':'strata','version':'0.1.8'}`.
- Full MCP sequence (initialize → initialized → tools/list): **all 18 tools register**.
- API grounded by introspecting the installed 2.0.0 SDK (module layout, MCPServer init
  signature, tool/run signatures) — not from memory or docs.

**Exact Next Steps:**
1. Twin gate + Codex on the PR; operator/Koa merges on clean per standing order.
2. Tag `v0.1.8` post-merge; watch the release run (publish + .mcpb).
3. Post-publish: fresh-index smoke (install ==0.1.8, handshake reports 0.1.8, mcp
   resolves 2.x).

## 2026-07-18 — bughunt/find-field-truncation-flag

**What changed:** Fixed the `strata_find_field` truncated-flag off-by-one in
`src/strata/mcp/tools.py`. `len(matches)` can never exceed the 50-item cap, so
`"truncated": len(matches) >= 50` wrongly reported `truncated=true` at exactly
50 matches (nothing was actually omitted). Now a `total` counter is
incremented for every match while `matches` still only appends the first 50;
`truncated = total > 50`.

**What was verified:**
- Added `test_strata_find_field_truncated_flag_false_at_exactly_fifty_matches`
  (50 matches → `truncated is False`).
- Negative control: stashed the source fix (kept the test) and confirmed the
  new test fails against the old `>= 50` logic.
- Full suite: 105 passed. `ruff check` and `mypy` clean on changed files.

**What remains / exact next step:**
- Direct push to `bughunt/find-field-truncation-flag` is blocked — it is
  currently this repo's default branch, and ruleset `main`
  (targets `~DEFAULT_BRANCH`, no bypass) requires all changes to land via PR.
  Opened PR #13 (`bughunt/find-field-truncation-flag-fix-truncated-boundary` →
  `bughunt/find-field-truncation-flag`) to carry the commit onto this branch;
  merging #13 updates PR #9 automatically. Left a status comment on PR #9;
  did not resolve the Codex thread there (out of scope for this task).
- Operator action needed: merge PR #13 (dispatched agents don't merge).

## 2026-08-16 — feat/pypi-strata-lookml

Commit: 117f9fb (pre-merge branch anchor — this repo squash-merges, so branch SHAs do
  not survive the merge; post-squash, resolve the landed anchor deterministically via
  `gh pr view 18 --json mergeCommit -q .mergeCommit.oid` and treat THAT as this block's
  commit for any HEAD reality check)
Conductor Mode: slice
Context Budget: medium
Context Loaded: AGENTS.md, conductor/AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/index.md, conductor/slice-04-pypi-packaging.md, handoff-log latest block.
Context Skipped: handoff-archive.md.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no stable tag required (first `v0.1.6` tag is the post-merge publish trigger, operator-pushed).

**Governing spec:** `conductor/slice-04-pypi-packaging.md` (authored at the review gate's
direction — PR #18 Codex P1 — as the in-repo contract for this work).

**What changed:** Packaged strata-oss for PyPI distribution as `strata-lookml`
(the names `strata` and `strata-mcp` are taken on PyPI by unrelated projects; the tool stays
"Strata" everywhere, console scripts `strata`/`strata-mcp`/`strata-chart` unchanged).

- `pyproject.toml`: `name = "strata-lookml"`, version `0.1.5` → `0.1.6`, and — found during
  head-side verification — **`mcp>=1.0,<2`**: mcp 2.0 removed `mcp.server.fastmcp`, which
  `src/strata/mcp/server.py` imports, so the previous unbounded pin made every fresh install
  pull an SDK the server cannot import (`strata-mcp` dead-on-arrival while the other two
  commands worked). Upper-bounded with an in-file comment; the 2.x migration is follow-up work.
- `src/strata/cli/main.py`: `click.version_option(package_name="strata-lookml")` — Click
  resolves installed metadata by exact distribution name; the stale `"strata"` made
  `strata --version` raise post-rename (PR #18 Codex P2).
- `.github/workflows/release.yml`: `publish-pypi` job (needs `build-and-release`) using PyPI
  Trusted Publishing (OIDC) via `pypa/gh-action-pypi-publish@release/v1` — no stored token;
  artifact handoff so publish consumes the already-built `dist/`; `.mcpb` bundle
  (`@anthropic-ai/mcpb` → `mcpb validate` → `mcpb pack`) attaching `strata-lookml.mcpb` to
  the GitHub Release.
- New `mcpb/` dir: spec-conformant `manifest.json` (`server.type: uv`, manifest 0.4), minimal
  `pyproject.toml` depending on `strata-lookml>=0.1.6`, 2-line `src/server.py` shim (the
  `.mcpb` `uv` runtime requires a local entry-point file; there is no published-package mode).
- `README.md`: Installation section (`uvx --from strata-lookml strata-mcp` — a bare
  `uvx strata-lookml` fails, no script matches the distribution name; `pipx`), Cursor +
  VS Code one-click install badges, top-of-file naming-split note.
- `.gitignore`: `*.mcpb`.
- Conductor: `slice-04-pypi-packaging.md` authored (status `review`), prior 07-18 handoff
  block moved to a new `conductor/handoff-archive.md`, `index.md` Active Slice pointer
  updated.

**What was verified — two-stage, honestly split:**

*Dispatch stage (sandboxed, no outbound network):* static only — TOML/JSON/YAML parsed,
`py_compile` clean, manifest hand-diffed against the live `modelcontextprotocol/mcpb` spec,
README regexes for `tests/test_docs_consistency.py` re-run by hand. Build/test explicitly
NOT run; disclosed rather than claimed.

*Head-side stage (full network, 2026-08-16):*
- `python -m build` → sdist + wheel build clean.
- **Fresh-venv wheel install** → `strata --version` reports `strata, version 0.1.6` (the P2
  fix, proven against installed metadata); `strata-chart` resolves; `strata-mcp` imports
  clean. This check is what CAUGHT the mcp 2.0 resolver break (resolver pulled mcp 2.0.0,
  `from mcp.server.fastmcp import FastMCP` failed; re-pinned `<2` → resolver picks 1.29.0,
  import clean, rebuilt + re-proven end-to-end).
- Full suite on an editable `[dev]` install: **106 passed**. `ruff check` clean on touched
  Python.
- Still unverified until the first tag push: the `publish-pypi` and `.mcpb` steps
  end-to-end (they can only run in CI on a tag) — watch that run, don't assume green.

**Operator prerequisite (blocking, before the first tag push):** configure the PyPI Trusted
Publisher at pypi.org — project `strata-lookml`, owner `G-Schumacher44`, repo `strata-oss`,
workflow `release.yml`, environment `pypi`. Without it `publish-pypi` fails closed with an
OIDC error — expected, not a bug (see the comment in `release.yml`).

**Also fixed on this branch (found by Apollo's required-checks blocker):** the
`tests/lookml/gcs_analytics` submodule pinned `cd9a4deb`, a commit its upstream no longer
has — the playground repo was recreated during the 2026-07-12 public bootstrap, orphaning
the pin, and `strata-ci` had never once run on `main`, so every PR checkout has been failing
at `actions/checkout` before tests could run. Repointed to the upstream head `f32aafa0`
(the playground's actual content — its repo holds 2 commits total). Suite re-run at the new
pin: 106 passed. Same dangling-ref shape as the pre-squash `anchor_ref` bug, third instance
of bootstrap-era rot (README URLs, default branch, now this).

**Panel round (operator-ordered pre-merge review: twins + philosophers, 2026-08-16):**
five parallel read-only reviewers. Verdicts: artemis SHIP · apollo ACCEPT · diogenes LEAN ·
socrates GO-WITH-GUARDRAILS · plato NEEDS-FORM (1 blocker). All findings addressed in one
batch commit:

- **plato BLOCKER — the self-targeting mirror job:** `release.yml` still carried the
  bootstrap-era `sync-to-oss` job. After this repo became canonical, that job SELF-TARGETED:
  on the same `v*.*.*` trigger as the release, it added this very repo as remote `public`,
  `git rm`'d every `.publicignore` path (including `conductor/handoff-log.md` and
  `slice-04` — files this PR wrote), and pushed the result onto our own `main`, with
  workflow-wide `contents: write` making `GITHUB_TOKEN` sufficient. The documented next
  step (push `v0.1.6`) would have fired it. **Job deleted** (history note left in the file);
  `docs/public-release.md` + `.github/workflows/public-release-audit.yml` (mirror-era,
  `public-v*`-triggered) deleted; `scripts/README.md` row updated. Residue
  (`.publicignore`, `scripts/check_public_release.py` + its tests) left for a follow-up
  issue — inert without the workflows, and removing the tests would churn suite counts in
  an already-long PR.
- **socrates + artemis (independently converged) — the blank PyPI page:** `pyproject.toml`
  had no `readme`, no `classifiers`, no `[project.urls]` — the built wheel's METADATA had
  ZERO Description; v0.1.6's page would have published blank and immutable. All three added;
  README's 8 relative image paths absolutized to `raw.githubusercontent.com` (PyPI does not
  rewrite relative paths); `[tool.hatch.build.targets.sdist]` added (anchored `/`-patterns —
  bare names glob at any depth; sdist went 317 files/6.8MB → 173 files, zero stray dirs);
  `mcp-name: io.github.g-schumacher44/strata` marker added for the future registry listing.
- **diogenes:** authoring-process "verification note" removed from the user-facing README
  (already recorded here).
- **plato should_fix:** pipx command-collision sentence added to the README naming note
  (the unrelated `strata-mcp` package installs a `strata` command; pipx shares one bin/).
- **notes:** `mcpb/README.md` stale step name fixed; `conductor/index.md` template-leftover
  header ("my-looker-project") fixed; `docs/README.md` dead `security-review.md` link fixed.
- **apollo hygiene:** `tests/test_mcp_tools.py` ruff-format (commit f331f1d) is hereby
  claimed in this log — it was changed-but-unclaimed in the earlier bullet list.

Re-verified after the batch: wheel METADATA carries Description (29.6k chars) + 7
classifiers + 3 Project-URLs with absolute image URLs; fresh-venv install → all three
commands; suite 106 passed; `ruff format --check` + `ruff check` clean tree-wide;
`release.yml` still valid YAML.

**Codex round 2 (post-panel head, 4 findings, all addressed):**
- *P1 release ordering:* the GitHub Release was created in the build job, BEFORE
  publish-pypi ran — a failed/misconfigured publish would leave a public Release whose
  `.mcpb` cannot start (its shim resolves `strata-lookml` from PyPI at launch).
  `release.yml` restructured to three jobs: `build` → `publish-pypi` → `github-release`;
  the Release now exists only after PyPI has the package. This also closes artemis's
  earlier first-minute-race note for good.
- *P2 shim pin:* `mcpb/pyproject.toml` pinned `strata-lookml==0.1.6` (was `>=0.1.6`,
  which would silently execute newer code under an artifact advertising 0.1.6).
- *P2 tag/version guard:* new fail-closed `Verify tag matches all version fields` step —
  refuses to build/publish when the tag disagrees with pyproject.toml, mcpb/manifest.json,
  or the shim pin. Proven both directions locally: passes at 0.1.6, refuses a wrong tag
  (negative control).
- *P1 Commit anchor:* the `Commit:` field below now carries a real seven-char hash
  (maintained one-behind by construction: the anchor names the last substantive commit;
  the anchor update itself is a docs-only commit).

Release procedure consequence, now that versions are pinned in three places: a release
bump touches pyproject.toml + mcpb/manifest.json + mcpb/pyproject.toml together, and the
guard refuses the tag if any is missed.

**Exact Next Steps:**
1. Operator: configure the PyPI Trusted Publisher (above), then merge PR #18.
2. Operator (or Koa on instruction): push tag `v0.1.6` — first end-to-end proof of
   publish-pypi + `.mcpb`; watch the run.
3. Post-publish: `uvx --from strata-lookml strata-mcp` against a real MCP client once
   (closes the last slice-04 acceptance box); spot-check the Cursor/VS Code badges.
4. Follow-up (separate slice): migrate `src/strata/mcp/server.py` off `mcp.server.fastmcp`
   so the `<2` pin can lift; then registry submissions (official MCP registry, awesome-lists)
   per the distribution research (koa library, 2026-08-16).

## 2026-08-17 — fix/audit-remediation-0.1.7

Commit: e8152aa (pre-merge branch anchor — this repo squash-merges, so branch SHAs do not
  survive the merge; post-squash resolve the landed anchor via
  `gh pr view 21 --json mergeCommit -q .mergeCommit.oid` and use THAT for any HEAD check)
Conductor Mode: full (escalated per CONDUCTOR_MODES.md triggers: root governance docs edited; cross-layer L1→MCP→outputs)
Context Budget: medium
Context Loaded: AGENTS.md (full authority order), conductor/CONDUCTOR_MODES.md, conductor/index.md, conductor/README.md, conductor/slice-05-audit-remediation.md, handoff-log latest block, docs/ files under edit, code seams (l1/enrich.py, mcp/server.py, outputs/dashboard.py). intent.md: not present in this repo's public tree (mirror-era exclusion) — noted rather than silently skipped.
Context Skipped: handoff-archive.md older entries.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no stable tag required; no tag pushed this slice (0.1.7 version bump only, prep for a future tag).

**Governing spec:** `conductor/slice-05-audit-remediation.md` (authored this session at the
operator's direct order — a claim-by-claim docs-vs-code audit of the just-published package
found 12 non-confirmed findings + 2 filed issues, all ordered fixed in one PR).

**What changed:** See commit e8152aa's message for the full breakdown. Summary:

- **The one real code fix (audit #22, README's flagship claim):** `l1/enrich.py`'s
  `pdt_ledger` status now computes a genuine `zombie` value — a PDT with real build facts
  and real consumers where every consumer is itself in the dead-code register. Previously
  status was set from usage alone and never cross-referenced deadness, so both
  `enterprise_mono` demo zombies (`pdt_attribution_full_funnel`, `pdt_customer_value_score`)
  rendered green "In Use" on the dashboard despite being the exact scenario the README
  advertises. Reuses the existing dead-code register (single source of truth) — does not
  re-derive deadness a second way. Wired through `outputs/dashboard.py` (distinct purple
  zombie badge/color/legend, not the same visual as plain `unused`), `outputs/artifacts.py`
  (cleanup roadmap now flags zombie cost too), and `mcp/tools.py` (additive
  `zombie_pdt_count` in `strata_usage_summary`, `unused_pdt_count`'s existing meaning left
  intact for backward compat).
- **serverInfo version (Closes #20):** `mcp/server.py` resolved the `mcp` SDK's version
  (1.29.0) in the initialize handshake because FastMCP 1.29's constructor has no `version`
  kwarg (verified by reading the installed SDK source, not guessed) — the low-level
  `Server.version` defaults to `None` and falls back to `importlib.metadata.version("mcp")`.
  Fix sets `server._mcp_server.version` post-construction from
  `importlib.metadata.version("strata-lookml")`, with a `PackageNotFoundError` fallback for
  editable/dev checkouts without an installed distribution record.
- **11 docs-truthfulness corrections** (README, docs/README.md, docs/security-hardening.md,
  docs/testing-findings.md, GOVERNANCE.md, AGENTS.md) — each verified against current repo
  state before editing, not just patched on the audit's say-so:
  - Fixture $ figures ($45,000/$18,750/~$765,000/yr) footnoted as hand-authored
    illustrative values, not products of the $5/TB formula shown beside them (verified: the
    formula applied to the fixture's own `bytes_processed` doesn't reproduce those numbers).
  - "14 domain skills" → 15 (filesystem-verified), **plus** a new generic
    `test_readme_domain_skills_count_matches_filesystem` in `test_docs_consistency.py` that
    regex-matches any `"N domain skills"` phrase and asserts it against the live
    `SKILLS_DIR` count — this class of drift is now machine-caught, not just this instance.
  - `docs/README.md`'s dead "Security Review — 3 HIGH, 6 MED" row deleted (that content was
    removed with the mirror era); Security Hardening row redescribed as what it is.
  - Dashboard screenshot alt text "10 schema drift records" → 14 (current reproducible
    count; matches the doc's own body text elsewhere).
  - `docs/testing-findings.md` Known Gaps: deleted the stale duplicate CTE row marked
    documented/unresolved — verified the fix is real at `resolver.py`'s `_sql_upstreams()`
    (the `✅ fixed` row was already correct).
  - "18 read-only tools" (4 spots) → truthful "18 tools — 17 read-only, 1 sandboxed"
    framing; `strata_render_chart` writes only to `~/.strata/output`/`/tmp`, never the
    LookML repo.
  - `docs/security-hardening.md` notification phrasing aligned with
    `docs/notifications-setup.md`'s honest "stops at payload generation" — verified
    `scripts/notify.py` literally exits 2 without `--dry-run`, no delivery code path exists
    at all (not just "gated").
  - `GOVERNANCE.md` + `AGENTS.md` read-only claims qualified with the same "as part of core
    analysis" carve-out `security-hardening.md` already used — verified `strata bootstrap`
    legitimately writes scaffolding (`conductor/`, `.mcp.json`, config), never `.lkml`.
  - "No false positives before you deprecate" softened to "designed to eliminate" +
    pointer to the FP classes `testing-findings.md` documents as fixed.
  - The unbacked "~82% smaller / ~30 round-trips" figure reworded to a qualitative claim
    (no benchmark script existed to back the precision; chose reword over fabricating one).
  - Haiku benchmark sections in `testing-findings.md` labeled one-off/manual/non-reproducible
    (date 2026-06-06, matching the doc's own stated verification date) instead of implying
    a pinned harness.
- **Mirror residue removed (Closes #19):** `.publicignore`, `scripts/check_public_release.py`,
  its test, and the `scripts/README.md` row — inert since PR #18 deleted the `sync-to-oss`
  workflow job that was their only consumer. Also cleaned two dangling comment references to
  `.publicignore` in `tests/test_mcp_tools.py` and `tests/fixtures/conductor/index.md` (same
  mirror-era rationale, now stale regardless of the file's existence).
- **Version bump to 0.1.7:** `pyproject.toml`, `mcpb/manifest.json`, `mcpb/pyproject.toml`
  shim pin, all together. Ran `release.yml`'s "Verify tag matches all version fields" Python
  block locally, verbatim: passes against tag `0.1.7`, refuses (exit 1, all three mismatches
  reported) against a wrong tag `0.1.8` — both directions proven, no tag pushed.

**What was verified:**
- Full suite: **106 → 107 passed** (removed 4 mirror-era tests with the D deletions; added
  5: `test_zombie_pdt_detection_enterprise_mono`, negative control
  `test_pdt_ledger_unused_status_unaffected_by_zombie_detection`, two in new
  `tests/test_mcp_server.py` for the serverInfo fix, one docs-consistency domain-skills-count
  test). Ran with `.venv/bin/pytest` against a fresh `uv venv` + `pip install -e ".[dev]"` —
  no prior `.venv` existed in this checkout.
- `ruff check src/ tests/ scripts/`: clean. `ruff format --check`: 173 files already
  formatted, clean.
- `mypy src/strata --ignore-missing-imports`: clean, 87 source files.
- `release.yml` re-parses as valid YAML after the historical-comment area was left untouched.
- Manually confirmed both `enterprise_mono` zombie PDTs report `status: "zombie"` via a
  direct `build_graph` + `build_dashboard_html` run, and that the rendered HTML contains
  both the `zombie-badge` CSS class and the `"status": "zombie"` JSON payload — not just
  asserted via the test, independently eyeballed the actual artifact.
- Confirmed `create_server(...)._mcp_server.version` reports the installed `strata-lookml`
  version (0.1.6 in this dev checkout, will be 0.1.7 once released) and is provably
  different from `importlib.metadata.version("mcp")` (1.29.0).

**Judgment calls beyond the literal task list (disclosed, not hidden):**
- Extended `outputs/artifacts.py`'s cleanup-roadmap condition from `status == "unused"` to
  `status in ("unused", "zombie")` — the roadmap's whole purpose is surfacing PDT cost for
  review, and leaving zombies out of it while fixing the ledger/dashboard would have been
  the same undercount bug relocated one hop over. No test pinned the old narrower behavior.
- Added `zombie_pdt_count` to `strata_usage_summary` as a new additive field rather than
  redefining `unused_pdt_count`'s existing meaning — avoids a silent breaking change to an
  already-published MCP tool contract for external consumers reading that field today.
- Did not touch `src/strata/skills/governance/strata_workflow.md`'s "zombie = unused OR
  dead-backed" framing (lines ~216-221) — it predates this fix, is now literally closer to
  true than before, and wasn't in the audit's 12-item list; flagging here rather than
  silently expanding scope.

**Pre-gate ritual:** run via `koa review --branch` before push, per the dispatch's mandatory
gate instructions — see PR body for the run's disposition (pass/findings-disclosed).

**Codex round 2 (P2, addressed):** the zombie verdict's `evidence_ids` cited only the PDT
node + build record while the verdict actually rests on every consumer's dead-code entry —
an un-auditable verdict in a dual-evidence tool. `_pdt_ledger` now appends
`dead:explore:<model.explore>` for each consumer on zombie records (same convention the
dead-views records already use), and the regression test asserts the full trail per zombie
plus a negative control (a `used` PDT must carry NO dead-explore evidence). Suite 107 passed.

**Codex round 3 (P2, addressed the thorough way):** correcting the alt text to "14" while
the PNG still visibly rendered "SCHEMA DRIFT 10" made the accessibility description lie about
the image. Rather than revert the text, the three dashboard screenshots were REGENERATED from
this branch's code (headless Chrome over CDP, enterprise_mono fixtures, original dimensions)
— and doing so surfaced one more real bug: the dead-code register names explores
MODEL-QUALIFIED while graph labels are bare, so `_build_graph_data`'s bare-name lookup missed
every dead explore — they rendered green/KEEP with QUERY COUNT 0 visible. Fixed at the single
source (qualified lookup in `_build_graph_data`; the tap handler now reads the node's own
`dead` flag instead of re-deriving), pinned by `test_graph_marks_dead_explores_dead` with a
live-explore negative control (verified: all 13 dead/zombie nodes flag). New screenshots show
the truthful state — dead_finance_v2 red with DEPRECATE, both zombie PDTs purple-badged with
their $-figures and dead consumers — and all three alt texts now describe exactly what the
images render. Suite 108 passed.

**Exact Next Steps:**
1. Operator: review and merge this PR (Closes #19, closes #20).
2. Operator (or Koa on instruction): once ready for a real release, push tag `v0.1.7` —
   this is the first tag since 0.1.6's publish; watch `publish-pypi` + `.mcpb` attach.
3. Post-merge: resolve this block's `Commit:` anchor to the squashed merge commit via
   `gh pr view <PR#> --json mergeCommit -q .mergeCommit.oid` (this repo squash-merges,
   branch SHAs don't survive) — update in the next docs-only commit, per convention.
4. Optional follow-up (not blocking, noted above): decide whether
   `strata_workflow.md`'s zombie-definition framing should be tightened now that the code
   emits a real `zombie` status distinct from `unused`.
