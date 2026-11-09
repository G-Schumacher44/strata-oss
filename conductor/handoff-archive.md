# Handoff Archive

Older handoff blocks moved out of the thin active log (`handoff-log.md` keeps the current block only — conductor/AGENTS.md).

## Date: 2026-11-08 — feat/wb-s5-findings (Findings triage page + keyboard map; workbench S5)

Commit: 1a3557e
  (Latest implementation commit: review round 4; earlier 5f12f51 (review round 3), 81b946f (merge of origin/main a0b5e1a (S6 #90) + the G19 single PR-comment builder; earlier 48bdcb0 (review round 2), earlier 363b5be (review round 1 + post-merge fix), 11f4739 (merge of origin/main 1cf80cb, S7 #89), 0c52ad7. The PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S5 of `workbench-spec-2026-11-08.md` (D1, D4, §4 Findings wireframe + keyboard map, §6b M2/M3/M6).
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D1, D4, §4, §5 S5, §6b), the operator-approved mockup (`mockups/workbench-mockup.html` + shot-findings*.png, shot-help.png), workbench/{app,index,render,server}.py + templates, triage.py, gate.py `finding_records`, links.py, outputs/dashboard.py palette, cli/findings.py, scripts/check_dashboard_js_syntax.py, tests/test_workbench_{server,render}.py.
Exact Next Steps: twin gate, operator merges. S6/S7 extend `_layout.html` (header bar, coverage strip, help dialog) and `assets/css/workbench.css`; S9 wires the disabled `a`/`u` buttons (`data-action="ack"|"unack"`, row ids in `data-ids`) to `POST /api/triage` with the `<meta name="strata-token">`; S8 adds Cmd-K (no button yet) and owns `/api/index.json`; S10 must render findings without `store.observe()` (the live page calls `triage_rows`, which observes).

### What changed

- `workbench/pages/findings.py` (new): `parse_query` (unknown status/category/page -> `InvalidInput`, a 400 page; page past the end clamps to the last), `group_rows` (M2: `dead:view:<pdt>` + `pdt:<pdt>` in the same status -> one item, PDT finding first; different statuses stay two rows), `findings_context` (tabs + counts honour the category/text filter, chips + counts honour the status/text filter, 200 items/page, `findings_href` keeps filters across links). Fixed / not-checked rows have no finding link (no current record). Per-item `data-comment` = PR-comment Markdown (location, rebuild cost over the usage window, `Workbench:` link only with a base URL — M7).
- `workbench/app.py`: `_findings` calls `triage_rows(graph, baseline, store)` per request (an ack from `strata ack` shows on reload; the store is opened once per App); cost comes from `finding_records` `cost_usd`. Coverage strip is now `(ran, text)` items: usage window, schema, content, baseline, `commit on branch (dirty)` from S13 provenance. Palette CSS vars come from `outputs.dashboard._palette_css()` (one source). `STATIC_ASSETS` gains `workbench.js` + `workbench.css` (`text/css`).
- Templates: `findings.html` (new); `_layout.html` gets the header bar (brand + repo, nav with `aria-current`, theme/help buttons hidden until JS), coverage dots, the CSS link, inline palette `<style>`, the one `<script src="/static/workbench.js" defer>`, and the `<dialog id="help">` keyboard map. `_base.html` unchanged.
- `assets/js/workbench.js` (new): progressive enhancement only, createElement/textContent, no HTML parsing. j/k, Enter/o, x, /, f (cycles non-empty chips by following their links), 1-6 (tab links), ?, g f/g o/g g, Esc (clear selection / blur filter; the dialog closes natively), c (PR comment of selected-or-cursor rows via `navigator.clipboard`), y (file:line), a/u -> toast pointing to `strata ack`. Theme toggle persisted in localStorage (try/catch; per-viewer convenience).
- `assets/css/workbench.css` (new): the mockup's dark tokens + light theme, Linear-style list, action bar, help dialog; status colours read the emitted `--n-*` vars.
- `scripts/check_dashboard_js_syntax.py`: also `node --check`s `workbench.js`. README dashboard section.

### Deviations from the brief

- Six status keys (`1`-`6`: New, Acknowledged, Baselined, Fixed, Not checked, All) as the brief lists, not the spec's `1-5` (the spec's map predates the not-checked tab).
- `Esc` "back" on non-findings pages is not wired: those pages are S6-S8's; on Findings Esc clears the selection.
- `c` copies directly (toast) rather than opening the mockup's preview modal.
- Tab/chip counts count list rows (a grouped PDT is one), matching what each tab lists.
- The page module lives at `workbench/pages/findings.py` per the spec (§5 S5), a new `pages` package.
- Shared layout changes landed in `_layout.html` rather than `_base.html`: `_base.html` also frames the escaping smoke template, whose guard test counts raw `<`/`>`/quotes, so the script/style tags belong in the page layout.

### Gates

After merging origin/main 1cf80cb (S7): pytest 636 passed, 1 skipped; ruff, format, mypy, JS syntax clean; reference regenerated (no change). Before the merge: pytest 624 passed, 1 skipped (base origin/main b7f7f7f: 597 passed, 1 skipped; +27 in `tests/test_workbench_findings.py`; `test_workbench_server.py` inertness check extended, `test_workbench_render.py` packaging checks cover every static asset); ruff check + format --check clean on src/ tests/ scripts/; mypy clean; `check_dashboard_js_syntax.py` passes (5 generated blocks + workbench.js); `gen_reference.py` produced no change. Fail-before: the new test file against a detached worktree of origin/main errors at collection (no `strata_lookml.workbench.pages`). Negative controls (mutation in this tree, restored from a copy): grouping disabled (3 fail), baseline not passed to `triage_rows` (2), status filter ignored (2), PR-comment link without a base (1), not-checked row linked (1). Guard controls in-suite: the sink scan catches 8 planted sinks in the real file; `_assert_inert` rejects another script src, an inline script, and the sanctioned src without `defer`.
Visual: headless Chrome (isolated profile) screenshots in `dev_project_tmp/wb-s5/` (findings-dark, findings-light, help, findings-grouped, findings-nojs) match the mockup; driven keys verified: j j x selects row 3, ? opens/Esc closes help, c and y write the expected clipboard text, a toasts the S9 hint, 2 -> `?status=acknowledged`, f -> next non-empty category, / focuses the filter, o opens `/finding/pdt%3A...`, g o -> `/overview`.

### Merge of origin/main 1cf80cb (S7 #89) and review round 1 (PR #91 @ 7418f28)

- Conflicts hand-resolved: `app.py` imports both `overview_context` and the findings page; `_assert_inert` tag/attr allowlists are the union (S7's table/SVG tags and SVG attributes added to S5's sets; S5's exact-script check kept); CHANGELOG keeps both Added entries; S7's handoff block moved to the top of `handoff-archive.md`.
- Integration bug found on the post-merge screenshot (`merged-overview.png`): the layout header's `.bar` rule hit S7's inline `svg.bar` and rendered every bar as a flex block. The header class is `.topbar` now; no other S5 selector matches an S7 class.
- Codex: completed, no findings. Artemis SHIP, one note: `CATEGORY_LABELS` must stay in step with the gate's categories. Fixed with `test_every_finding_category_has_a_label` (negative control: dropping `drift` from the dict fails it). Apollo ACCEPT_WITH_NOTES: its notes say the gate counts and screenshots can't be checked from a static diff, which is true. Evidence is in this block and the PR report.
- Not changed: S7's `overview.html` keeps its own inline palette (`prefers-color-scheme`) and so does not follow the workbench theme toggle. Aligning it with `workbench.css` tokens is a follow-up for S7/S10.

### Review round 2 (PR #91 @ e2638a7)

- Codex P2 (`_layout.html`: the help `<dialog>` had no clickable close, so mouse and touch users could not dismiss it): fixed in 48bdcb0. Added a `<form method="dialog">` Close button (`aria-label="Close help"`), which closes natively with no JS. `workbench.js` also closes on a click outside the dialog box; a click on the dialog's own padding still targets the dialog, so the bounding box decides. New test `test_help_dialog_has_a_close_button_that_works_without_javascript`. Headless Chrome: the Close button closes it; a click on the padding keeps it open; a backdrop click closes it; on a page loaded with JS off, Close still closes it. pytest 637 passed, 1 skipped; ruff, format, mypy and JS syntax are clean; the sink scan is still clean.

### Merge of origin/main a0b5e1a (S6 #90) and G19: one PR-comment builder

- Conflicts hand-resolved: `app.py` imports and `STATIC_ASSETS` carry both slices' entries (workbench.js, workbench.css, detail.js). The `_assert_inert` tag and attribute sets are the union (adds S6's aside/textarea/pre and `readonly`). Scripts stay strict: a page may load only `/static/workbench.js` and `/static/detail.js`, each at most once, and no other `<script` may appear. S6's handoff block moved to the top of `handoff-archive.md`.
- G19: there is one PR-comment builder, `workbench/pr_text.pr_comment`. Findings' `c` fetches `GET /api/pr-comment?id=...` (read-only, text/plain, nosniff, behind the Host check). It returns `pr_comment` over the current records of the selected ids. Fixed and not-checked ids have no record and are skipped; if none remain the response is 404 and the page shows a toast. The copy uses a `ClipboardItem` holding the fetch promise, so the keypress's user activation survives the fetch, with a fallback of `writeText` once the text arrives.
- Deleted: `pages/findings._comment_lines`, the row `data-comment` attribute and the section's `data-comment-head`. The page's own `CATEGORY_LABELS` and `_usd` are gone too; the chips and cost column use `pr_text.CATEGORY_LABELS` / `pr_text.usd`, so drift chips now read "schema drift".
- Findings now reads rows through S6's `App._triage_rows` (one per-request read); my duplicate `_store` cached_property is removed (S6 opens the store in `__init__`).
- `check_dashboard_js_syntax.py` now checks every hand-written `assets/js/*.js` (workbench.js and detail.js), skipping the vendored `*.min.js`.
- Tests: `test_the_list_copies_the_one_pr_comment_builder` checks the endpoint text equals `pr_comment(...)` byte for byte for the grouped PDT row. The no-base vs base link test now goes through the endpoint. `test_pr_comment_skips_ids_without_a_current_record` checks fixed-only and empty requests get 404 and a mixed request skips the fixed id. The label test checks `pr_text.CATEGORY_LABELS` covers every category.
- Headless Chrome: `c` on the grouped PDT row copied exactly the pr_comment text ("**Strata** found 2 LookML findings: ..."). `c` on a fixed row shows the no-record toast. Detail pages load workbench.js then detail.js with no console errors, and `?` opens help there (screenshots merged2-findings.png, merged2-detail.png).
- Gates: pytest 666 passed, 1 skipped; ruff, ruff format, mypy clean; JS syntax 5 generated blocks + 2 static scripts; reference regenerated (no change).

### Review round 3 (twins @ dad6880)

- Artemis should_fix (only `_findings` passed `nav=`, so Overview/Graph/Search never marked their nav link current): fixed in 5f12f51. `_placeholder` takes `nav`, and `_overview`, `_graph` and `_search` pass theirs; detail and error pages intentionally mark none. New parametrized test `test_each_top_level_page_marks_its_own_nav_link_current`; negative control: dropping `nav="overview"` fails its case.
- Apollo note on "+27": that count was right when written. 624 − 597 = 27 at 0c52ad7. Round 1 added the label test and round 2 the dialog test, hence 29 items at dad6880. Count now: pytest 670 passed, 1 skipped (after the S6 merge and this round).

### Review round 4 (Codex P2 on #91)

- Codex P2 (`workbench.js`: ids were space-joined in `data-ids` and split on spaces, so an id with a space, e.g. `schema:missing_table:p.d.Order Details` from a quoted table name, became bogus ids and was 404'd or dropped from the PR comment): fixed in 1a3557e. `data-ids` and `data-locations` are now JSON arrays built with `json.dumps` in `pages/findings.py`; Jinja autoescapes them into the attribute, with `"` written as `&#34;`. Jinja's `|tojson` is not used because it leaves `"` raw, which would break a double-quoted attribute. `workbench.js` reads them with `jsonList` (JSON.parse, strings only) and never splits text.
- Tests: `test_an_id_with_a_space_reaches_the_comment_endpoint_intact` uses a real fixture (view on `` `p.d.Order Details` `` with schema facts lacking it). It checks the row carries the exact id, the endpoint returns 200 and quotes it, and the space-split halves would 404. The grouped PDT row still sends both ids (`test_the_list_copies_the_one_pr_comment_builder`). `test_workbench_js_never_splits_ids_on_whitespace` pins the parse.
- Negative controls: putting the JS `split(" ")` back fails the split test; emitting a non-JSON `data-ids` fails 10 tests. Headless Chrome on the spaced fixture: `c` copied "**Strata** found 1 LookML finding: ... `schema:missing_table:p.d.Order Details`".
- Gates: pytest 672 passed, 1 skipped; ruff, ruff format, mypy, JS syntax (2 static scripts) clean; reference regenerated (no change).

## Date: 2026-11-08 — feat/wb-s6-detail (detail pages; workbench S6)

Commit: ba11d3c
  (Latest implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S6 of `workbench-spec-2026-11-08.md` (D2 page-to-reads table, §4 Detail wireframe, §6b M5/M7).
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D2, §4, §5 S6, §6b), the approved mockup (detail frame CSS, `detailFrame`, `prText`), workbench/{app,index,render}.py + templates, links.py, gate.py, mcp/tools.py `strata_object`, synthesis/{slices,verdicts}.py, outputs/artifacts.py, tests/test_workbench_server.py.
Exact Next Steps: twin gate, operator merges. S5 (findings) and S7 (overview) share `_layout.html` / `_base.html`: the detail frame carries its own scoped CSS (`.detail`) and only the `head` block is extended, so a layout restyle should not collide. S9 turns the disabled Acknowledge buttons on (`_lineage.html` `finding_cards`).

### What changed

- `workbench/detail.py`: `Detail(workbench, roadmap)` builds plain-data view models (no markup): `object_page(obj)` and `finding_page(id, records)`. Verdict: explore = `deterministic_verdict(build_explore_slice(...))`; everything else = the first matching `cleanup_roadmap` item (a table also matches roadmap items whose evidence names its `schema_table:`), else "NO ACTION". Lineage groups come from `strata_object` upstream/downstream, each member a link only when its node exists and has a page (explore keys resolve through `explores_by_key`; an ambiguous key links to its candidates page). Marks: `dead` / `zombie` from the findings on the node (a view also reads its `pdt:` node; zombie wins). Content: `content is None` or `content_checked` false -> "not loaded" note, never a 0.
- PDT pages: a `missing_build_facts` ledger entry (placeholder zeros) renders "Build facts: not loaded for this PDT", never $0 or 0 builds (Codex P2).
- Roadmap actions attach to a page by node identity: an item's first evidence id is its subject node, so a table and an explore sharing a dotted name no longer share an action (Codex P2); a table still also takes drift items whose evidence names it.
- Explore usage: "Last queried" reads "never" only for a measured zero count, "not recorded" for a count with no timestamp (Codex P2); scanned detail.py for other None-to-value turns (type "unknown" is honest; nothing else found).
- `workbench/pr_text.py`: `pr_comment(records, obj, workbench_base=None, verdict=None) -> str`, pure, shaped like the mockup's `prText`; no base -> no `Workbench:` line (M7); no records -> a comment about the object with its verdict. Also owns `CATEGORY_LABELS`, `ACTION_LABELS`, `CATEGORY_ACTIONS`, `usd`.
- `outputs/artifacts.py`: `_cleanup_roadmap` -> public `cleanup_roadmap`, unchanged behaviour.
- Templates: `_detail_frame.html` (scoped CSS from the mockup tokens, light/dark by `prefers-color-scheme`, crumbs, header, verdict, side cards, readonly PR-comment textarea), `_lineage.html` macros, `detail.html`, `finding.html`. No inline script or style attributes.
- `assets/js/detail.js` (allow-listed as `/static/detail.js`): copy buttons via `data-copy` / `data-copy-from`, textContent only.
- Status pills are `triage_rows`' (the one source), read fresh per request so a CLI `strata ack` shows without a restart; acknowledged shows `acked_at` and the note. `App` opens a `TriageStore` on the graph. Only the Acknowledge button waits for S9.
- `app.py`: `_object` / `_finding` render the new pages; ambiguous/unknown behaviour unchanged (300/404/400).

### Deviations from the brief

- No "Open in graph" link (the graph page is still a placeholder; S8).
- Rebuild cost in the PR comment has no "over N days" suffix (the finding record carries no window).
- The hostile-fixture test now allows exactly one external script tag (`/static/detail.js`) and the frame's tags/attributes; any other script still fails it.

### Gates

pytest 619 passed, 1 skipped (22 new in `tests/test_workbench_detail.py`); ruff check + format --check clean; mypy clean; `check_dashboard_js_syntax.py` passes; `node --check` on detail.js; `gen_reference.py --check` clean. Fail-before: the new test file against a detached worktree of origin/main (b7f7f7f, PYTHONPATH pinned to it; the import of `cleanup_roadmap` and `pr_comment` stubbed so it collects) -> 21 failed, 1 passed (the roadmap one).

## Date: 2026-11-08 — feat/wb-s7-overview (Overview as a written report; workbench S7)

Commit: 49ce93c
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S7 of `workbench-spec-2026-11-08.md` (D1 inline SVG, D2 Overview reads, §4 Overview wireframe).
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D1, D2, §4, §5 S7), the approved mockup + shot-overview.png, workbench/{app,render,index}.py + templates, mcp/tools.py (usage/pdt/drift), outputs/artifacts.py, l1/enrich.py, links.py.
Exact Next Steps: twin gate, operator merges. S10 deletes the old dashboard (and its Chart.js); S11/S6 consume the same `links.py` paths.

### What changed

- `workbench/overview.py`: `overview_context(wb)` lifts numbers and rows from `strata_ir_status`, `strata_usage_summary`, `strata_pdt_costs`, `strata_schema_drift`, `cleanup_roadmap` and the findings index; it formats and links (`links.object_path`), nothing else. Each section's `ran` flag is `analysis_coverage`.
- `templates/overview.html`: the fixed sentence templates. A section whose check did not run says "Not run — load <X> facts" in place of any number (headline findings read "findings not run" when neither check ran and none exist; never "0"). Content facts missing: the dead sentence says "no queries" only and names the missing facts. PDT build facts missing: "Not run — load PDT build facts".
- Window label comes from `period.days`: "30 days" only when the facts say 30; another length prints as is; no period prints "length not recorded". Never "/mo" (the label half of spec N8).
- `workbench/charts.py`: `bar(value, total, width, height)` emits SVG with numeric attributes and fixed literals only (no text, no label; bools, NaN, inf, strings raise). The page passes it through `render.safe_svg`, still the only `Markup` site. Colour is CSS on the section.
- `outputs/artifacts.py`: `_cleanup_roadmap` is now public `cleanup_roadmap` (spec D2); one caller updated.
- `app._overview` renders `overview.html`; the placeholder facts are gone. No Chart.js in the workbench; the old dashboard is untouched (S10).
- `tests/test_workbench_server.py`: the hostile-fixture tag/attribute allowlist grew by the report's structural tags (table, strong, svg, rect, span, ...) and numeric SVG attributes; `img`/`script`/`on*` remain forbidden.

### Deviations from the brief

- The top-explores share lives in the read layer: `strata_usage_summary` gained `top_explores: [{explore_key, queries, share}]` (top 6, share = queries / total_queries; None when usage was not checked), so MCP/CLI get it too; the overview only renders it (the sentence names the busiest explore's share).
- Drift sentence counts field-to-column references, so it reads "N missing-column references" (Codex P2: it had read as distinct columns); no counting added to overview.py.
- Next-actions links go to each object's page via `evidence_ids[0]`; finding-page links wait for S5/S6.

### Gates

pytest 607 passed, 1 skipped; ruff check + format --check clean; mypy clean; `gen_reference.py --check` and `check_dashboard_js_syntax.py` clean. Fail-before: `tests/test_workbench_overview.py` against origin/main (detached worktree) errors at collection (no `workbench.overview`). Negative control: forcing the usage section's `ran` to True fails `test_not_run_without_facts_never_zero` and `test_mutation_flipping_coverage_changes_the_sentence`; reverted, 8 pass. Screenshots: /Volumes/t9/dev/dev_project_tmp/wb-s7/{full,notrun}.png.

## Date: 2026-11-08 — feat/wb-s4-server (local server, route table, security headers; workbench S4)

Commit: 2efc749
  (Latest implementation commit: Codex round 1 fix; earlier d0e98d2 (merge of origin/main 46b3214, S4c #87), 047f0da (merge of S11 #86 + the switch to `config.load_workbench_url`), 7b21e95, ceb7abd. The PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S4 of `workbench-spec-2026-11-08.md` (D1, D3, D6, D8, §4 URL map, §6a Q1).
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D1-D8, §4, §5 S4, §6a/§6b), cli/dashboard.py, loopback.py, workbench/render.py + templates, links.py, triage.py, gate.py, identifiers.py, pipeline.py, ir/store.py, config.py, errors.py, mcp/tools.py `strata_object`, the dashboard Host/port tests.
Exact Next Steps: twin gate, operator merges. Then S5 (findings landing: `triage_rows` over `Workbench`, replaces `_findings`), S6 (detail pages: replace `_object` / `_finding` placeholders), S7 (overview), S8 (graph + `/api/index.json` Cmd-K shape), S11 landed first (#86); the workbench resolves its base through the same `config.load_workbench_url`. S9 adds `POST /api/triage` to `App.respond` (method gate + the token already exposed in the `<meta>`).

### What changed

- `workbench/app.py`: `App(workbench, hosts, token, staleness).respond(method, target, host) -> Response(status, headers, body)`. Order: Host allow-list (refused -> plain-text 403, never a page, so never the token) -> method (GET/HEAD; else 405 + `Allow`) -> route. Routes: `/` 302 `/findings`; `/findings`, `/overview`, `/graph`, `/search`, `/api/index.json`; `/<kind>/<one percent-decoded segment>` for explore/view/pdt/table/field (via `strata_object`), finding (1..n records from the index), static (fixed `STATIC_ASSETS` map: cytoscape, dagre, cytoscape-dagre). `NotFound` -> 404 error page, `InvalidInput` -> 400, ambiguous explore/table -> 300 candidates page with links built by `links.object_path`. `SECURITY_HEADERS` (CSP exactly per D6, nosniff, no-referrer, plus `Cache-Control: no-store`) are added by the one `_response` builder every response goes through. JSON goes through `_embed_json` (`<` escaped).
- `workbench/server.py`: `make_handler(app)` -> a `BaseHTTPRequestHandler` (no SimpleHTTPRequestHandler, no chdir, no directory serving). Unknown methods reach `send_error(501)` before any `do_*`; that is routed through the app so they get the Host check and a 405. Malformed requests get a bare error with the security headers. Unexpected exceptions -> traceback on stderr + bare 500. `new_token()` = `secrets.token_urlsafe(32)`, once per process.
- `workbench/index.py`: `load_graph` = `describe_inputs` (read first) + `load_or_build(repo, usage, schema, load_cache_path(repo), CACHE_MAX_AGE_SECONDS)`; `index_graph` builds the frozen `Workbench` (records, findings_by_id 1..n, findings_by_node, coverage, source provenance, baseline, base_url, inputs). `Staleness` re-fingerprints at most every 10 s, sticky; the layout shows a restart banner.
- Templates: `_base.html` gains a `head` block; `_layout.html` (token `<meta>`, nav, coverage strip, stale banner), `placeholder.html`, `candidates.html`, `error.html`.
- CLI: `cli/workbench.py` defines `strata workbench` (dashboard's options + `--baseline` read-only + `--workbench-url`, resolved by S11's `config.load_workbench_url`: flag -> `STRATA_WORKBENCH_URL` -> config `workbench_url`; an invalid base exits 1 with its hint) and `strata dashboard` as an alias `click.Command` sharing its params/callback. `--out` runs `cli.dashboard.export_and_serve` (the old command body, unchanged apart from taking `explicit` as a parameter). `bind_server` gained `handler_factory` (default: the legacy static handler), so port fallback and the per-port Host allow-list are shared.
- One source per rule: `gate.findings_by_node(records)` (subject node + table drift via `schema_table:` evidence) is now the only node->findings rule; `strata_object._node_finding_ids` routes through it. `identifiers.explore_matches` / `table_matches` are the candidate lists `resolve_explore` / `resolve_table` already used inside. `pipeline.CACHE_MAX_AGE_SECONDS` (300) moved from `mcp/server.py` (re-imported there).
- Docs: reference regenerated; README CLI table + dashboard section; runbook; enterprise-deployment; security-hardening (writes table, Listening bullet, new "Workbench Server" section). CHANGELOG Security/Added/Changed.

### Deviations from the brief

- `--out` with `--baseline` / `--workbench-url` is a usage error (exit 2): those flags only mean something to the live server.
- `strata dashboard` without `--out` no longer writes `./output/<repo>` (it is the workbench now). The legacy `make_handler` + `export_and_serve` stay in `cli/dashboard.py` for `--out` until S10; the existing Host tests exercise that legacy handler and pass unchanged.
- `--workbench-url` warning: rather than "warn when fallen back", it warns whenever the URL names an explicit port other than the one bound (covers fallback precisely; silent for export-form or portless bases).
- Ambiguous names answer 300 Multiple Choices (body = candidates page), not 200.
- `/api/index.json` is a minimal `{objects: [{kind, name, path}], findings: [{id, path}]}`; S8 owns its final shape.
- Known gap, predates this slice (not filed — the brief forbids creating issues): `identifiers.resolve_field` splits `view.field` at the first dot, so a field of a view whose quoted name makes a side empty (e.g. view `..`) has no page (clean 400), and a dotted view name resolves the field node but reports the wrong `view` upstream. The round-trip test pins the 400.

### Gates

pytest 597 passed, 1 skipped after merging origin/main 46b3214 and review round 1 (this slice adds 73, all in `tests/test_workbench_server.py`; before the merge 568 vs base 4895c78's 498); ruff check + format --check clean on src/ tests/ scripts/; mypy `src/strata_lookml --ignore-missing-imports` clean; `check_dashboard_js_syntax.py` passes (5 blocks); `gen_reference.py --check` clean. Fail-before: the new test file against origin/main (detached worktree, PYTHONPATH pinned to it) errors at collection (no `strata_lookml.workbench.app`). Negative controls, each a mutation in a throwaway detached worktree of 7b21e95, run over `test_workbench_server.py` + `test_strata_object.py`: Host check removed (8 fail), security headers dropped (23), POST/PUT/... allowed (10), static served from the package directory by name (3), segment not unquoted (3), token in the 403 body (6), candidates page removed (3), error hint dropped (9), every start rebuilds instead of `load_or_build` (1), staleness checked every request (1), staleness not sticky (1), `|safe` in `placeholder.html` (1, the hostile-fixture test), 501 not routed through the app (8), table drift dropped from `findings_by_node` (1).

### Review round 1 (PR #88 @ 149732d)

- Codex P2 (canonical explore URLs went through the shorthand resolver: `resolve_explore` splits `model.explore` at the first dot, so model `retail.v2` 404'd, and a bare explore literally named `retail.orders` in another model captured `/explore/retail.orders`): fixed. `identifiers.explores_by_key(graph, key)` matches the published `explore_key(model, explore)` whole; the explore route uses it first and calls `strata_object(..., model=)` (new optional argument, passed to `resolve_explore`); only a key no explore has falls back to the shorthand (hand-typed `/explore/orders`). Two pairs spelling one key give a candidates page. New `test_canonical_explore_keys_resolve_exactly` (dotted model, the literal-name trap, shorthand still a 300) fails on 149732d (detached worktree) and passes here; the hostile round-trip test now also asserts each object page shows that node's own id.
- Known limit, not changed: two pairs that spell the same key (model `a.b` + explore `c`, model `a` + explore `b.c`) share one URL, so their candidate links are identical; the URL scheme (D3) has no way to tell them apart.

## Date: 2026-11-08 — feat/wb-s4c-cli-triage (strata findings / ack / unack, workbench S4c)

Commit: 545c3a8
  (Latest implementation commit, review round 2; first 1c384bc; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S4c of `workbench-spec-2026-11-08.md` (§6b Q6, "cheap TUI first").
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, cli/AGENTS.md, cli/{check,main,_contract}.py, triage.py, gate.py, pipeline.py, mcp/server.py, config.py.
Exact Next Steps: twin gate, operator merges. S4 (server) and S11 (links out) are independent of this.

### What changed

- `cli/findings.py`: `strata findings` (`--repo`/fixtures with envvars, `--baseline`, `--status` default new, `--category`, `--format table|lines|json`), `strata ack ID... [--note]`, `strata unack ID...`. Thin over `triage_rows` / `TriageStore`; the graph loads through `load_or_build` + `load_cache_path` with the MCP server's `CACHE_MAX_AGE_SECONDS`.
- `lines` = `file:line: [category] label — message (id)`, one per row; no file (or line) prints `-:0:`. Verified against real `vim -q` (entries resolve to file and line) and a Python re of `%f:%l:%m`. Paths are repo-root-relative, so vim runs from the repo root.
- `ack`/`unack`: `-` reads ids from stdin (one per line, blanks skipped); output is one line per id (`acknowledged` / `already acknowledged` / `unacknowledged` / `not acknowledged`); unknown id -> `InvalidInput` exit 1, nothing written (store enforces). README "Triage from the terminal" has the fzf (`sed -E 's/.* \((.*)\)$/\1/'`) and vim recipes; command table and cli/AGENTS.md updated; docs/reference.md regenerated.

- Review round 1 (head): `_contract.JsonCommand` now treats a `--format json` option (param `fmt`) as JSON mode, like `--json`; `findings` uses it, so `--format json` errors are the `{error, code, hint}` envelope on stdout (table/lines keep stderr text). Test in `tests/test_cli_triage.py`.

- Review round 2 (head, after S11 #86 merged): `strata findings --workbench-url` via `config.load_workbench_url` + `links.finding_path/link`; with a base, `lines` appends ` <url>` after the id, `table` appends the URL to the finding cell, `json` rows gain `url`; no base, unchanged. The fzf `sed` now tolerates the trailing ` <url>`. Merged origin/main `7fe8bb5`; S11's block moved to the archive.

### Deviations from the brief

- Id extraction one-liner uses `sed`, not `cut`/`awk`: labels contain spaces, and the id is the trailing parenthesised field.
- `JsonCommand` is used via the `--format json` rule above (no envelope for table/lines).
- A table run prints its count to stderr, so stdout stays only the rows.

### Gates

pytest 524 passed, 1 skipped; ruff check + format --check clean; mypy src clean. Negative control: the 12 new tests run against a detached origin/main worktree: 11 fail (no such command), the 12th (no ids -> exit 2) passes by coincidence. New tests: `tests/test_cli_triage.py`.

## Date: 2026-11-08 — feat/wb-s11-links (links out, workbench S11)

Commit: a3a125a
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S11 of `workbench-spec-2026-11-08.md` (D3 base URL rules, §6b M7).
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D3, S11, M7), links.py, config.py, cli/check.py, outputs/pr_report.py, scripts/pr_comment.py, mcp/server.py, mcp/tools.py.
Exact Next Steps: twin gate, operator merges. Then S4c: `strata findings` should call `load_workbench_url` + `links.link(base, finding_path(id))` once it lands (TODO: not on main at S11 time, not implemented here). S4 server and the TUI `w` key reuse the same resolver.

### What changed

- `config.load_workbench_url(flag=None)`: the one resolver. Precedence `--workbench-url` > `STRATA_WORKBENCH_URL` > config `workbench_url`; None when unset (never guessed). Valid = `http(s)://…`, or a path ending `.html` / containing `#`; else `InvalidInput` with a hint (CLI exit 1).
- `strata check`: `--workbench-url`; with a base each failure gets `url` (`finding_path`, joined by `links.link`) in `--json`, and text lines append `<url>`.
- `outputs/pr_report.build_pr_comment(..., workbench_base=None)`: explore bullets link to `/explore/<model>.<explore>`; `scripts/pr_comment.py --workbench-url` (env/config fallback).
- MCP `strata_object` (server wrapper only, so `tools.strata_object` and `strata query object` are unchanged): adds `workbench_url` (object page) when a base resolves from env/config.
- No base: no `url` / `workbench_url` keys and no links anywhere.

### Deviations from the brief

- MCP: only `strata_object` gains `workbench_url`. The other finding-bearing tools (dead-code register, drift) return item lists with no uniform finding id or object node id, so a link there would be a guess; left out.
- `--workbench-url` has no click `envvar=`: `load_workbench_url` reads the env itself so precedence lives in one place.
- `strata findings` not on main: nothing added.

### Gates

pytest full green; ruff check + format --check clean; mypy `src/strata_lookml --ignore-missing-imports` clean; `gen_reference.py` regenerated. No-base `check --json` output byte-identical between origin/main (detached worktree) and this branch (`cmp`); the `strata query object` / MCP-vs-CLI equality test and the existing JSON goldens still pass. Fail-before: `tests/test_workbench_links.py` against origin/main errors at collection (no `load_workbench_url`).

## Date: 2026-11-08 — feat/wb-s4b-triage-core (triage core and link builder, workbench S4b)

Commit: 3dc79ff
  (Latest implementation commit, review round 3; earlier 8dba45c, f6d0d50, 629002d. The PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S4b of `workbench-spec-2026-11-08.md` (D2, D3, D4; mockup items M6, M8).
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D2-D4, S4b, §6b) and validation report (M6, M8), gate.py, config.py, safe_paths.py, errors.py, ir/store.py, ir/types.py, identifiers.py, l1/enrich.py, cli/check.py.
Exact Next Steps: twin gate, operator merges. Then S4 (router + server) consumes `triage_rows` and `links`; S4c (`strata findings --format lines` + `strata ack`/`unack`) and S11 (links out) can follow S4b directly.

### What changed

- `triage.py`: `TriageStore.open(repo, graph)` at `config.triage_path(repo)` = `~/.strata/triage/<repo_key>.json` (dir via `ensure_private_dir`, file 0600, write via `check_write_destination` + temp + `os.replace`). Document `{version, rev, ids: {id: {category, acked_at, note?, unacked_at?, first_absent_at?}}}`. `.acknowledge(ids, note=None)`, `.unacknowledge(ids)`, `.snapshot()`, `.observe()`.
- Append-only (M8): unack sets `unacked_at`; re-ack clears it. `observe()` stamps `first_absent_at` the first time a stored id is absent from a category whose check ran, clears it when the id reappears, and prunes the entry once absent for 90 days (`ABSENT_TTL`). A category that did not run is never stamped.
- Concurrency: writers are serialized by an OS advisory lock on a dedicated `<store>.lock` (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows; 0600, write-guarded by `check_write_destination`, opened `O_NOFOLLOW`, never deleted, never written), held around the rev check and `os.replace`. The kernel releases it when the holder dies, so there is no stale-lock handling. The rev check stays as defence in depth: re-read, apply per id, write `rev+1`, replace only if the on-disk `rev` is still the one read; 3 tries (50/100 ms backoff) then `StrataError("triage state changed concurrently", hint="retry")`. On Windows `msvcrt` gives up after ~10 s -> `StrataError("triage store is locked by another writer", hint="retry")`.
- Allowlist: `acknowledge` accepts an id only if a current finding carries it or the store already holds it; `unacknowledge` only stored ids. Any miss -> `InvalidInput`, nothing written. Notes cap at 2000 chars.
- `triage_rows(graph, baseline, store)`: frozen `TriageRow`s, status derived once (D4): baselined (wins over acknowledged, ack record kept, M6) / acknowledged / new for current ids; then acked or baselined ids absent now: fixed when their category ran, not_checked when it did not. Checked categories come from each category's own facts (`FINDING_CATEGORIES` over `analysis_coverage`): usage for dead-code / unused-pdt / zombie-pdt, schema for drift; G16's `content` flag feeds dead code but gates nothing. Integrity counts as always checked.
- `links.py`: `object_path` (explore/view/pdt/table/field; None for kinds with no page), `finding_path` (`quote(id, safe="")`), `link(base, path)` (no base -> None; `.html` or `#` base -> `<base>#/<path>` replacing any old fragment; else `<base>/<path>`).
- Import-graph guard (`tests/test_triage.py`): AST walk of strata_lookml's own import closure from triage, links, gate and mcp/tools (function-level imports too) bans `http`, `textual`, `jinja2`, `strata_lookml.workbench`, `strata_lookml.tui`; a second assertion keeps `strata_lookml.triage` out of the gate's closure.

### Deviations from the brief

- `TriageStore.open(repo, graph)`, not `open(repo)`: the allowlist (D4: "enforced in the store") needs the current finding ids, and `observe()` needs which categories ran. `triage_rows` refuses (ValueError) a store opened on a different graph.
- Each entry also stores its `category` (taken from the current finding at ack time): "fixed" vs "not checked" for an absent acked id depends on whether its category ran, which the id alone does not say.
- `first_absent_at` is stamped on every stored entry, unacked ones included, so the 90-day TTL also prunes unacked records (otherwise they would never leave the append-only store).
- `triage_rows` calls `store.observe()`, so reading rows can write the store (only when an absence stamp or prune changed something). No file is created when nothing is stored.
- One row per id: a duplicated id (G14) is one row with its first record's label, subject and line; `/finding/<id>` (S6) shows all records.
- HOME is redirected per test module (`_home` fixture in `tests/test_triage.py`), not globally in conftest, so other suites' HOME handling is unchanged.

### Review round 1 (PR #85)

- Codex P2 (rev check and replace not mutually exclusive: two writers that both read rev 0 could both succeed, the last silently dropping the other's ids): fixed with the O_EXCL lock above. New test races a second writer between the first's check and its replace; it now raises instead of landing and being overwritten. Stale-lock and fresh-lock behaviour tested.
- Artemis should_fix (note validation untested): `test_acknowledge_refuses_a_bad_note` (non-string, over 2000 chars; exactly 2000 accepted).
- Apollo ACCEPT (note: could not re-run gates read-only).

### Review round 2 (PR #85 @ ae6b416)

- Codex P2 + Artemis should_fix (stale-lock recovery races: A stats a stale lock, B breaks it and takes a fresh one, A unlinks B's live lock): fixed by never breaking the lock. Conservative choice over an fcntl/msvcrt lock, which D4 rules out; the cost is a manual delete after a SIGKILL in a one-read-one-rename window.
- Artemis note (lock contention reported as "changed concurrently"): contention now raises its own "locked by another writer" error.
- Codex P2 (an old `first_absent_at` survived re-acknowledging a present id, so the TTL could prune a fresh ack a day later): `acknowledge` clears it when the graph shows the id present.
- Apollo ACCEPT_WITH_NOTES (could not re-run gates read-only).

### Review round 3 (head direction, superseding round 2's lock)

- Shape fix for the stale-lock race: the O_EXCL lock file and its no-break / staleness handling are gone; an OS advisory lock (above) replaces them. The spec's "no fcntl" (D4) assumed no Windows path; `msvcrt.locking` covers Windows.
- Tests: the cross-writer race test now runs the second writer in a thread blocked on the lock while the first sits between its check and its replace (both land, rev 2); a child process that takes the lock and is SIGKILLed never blocks the next writer (and a live holder really blocks a non-blocking probe); the lock file is never deleted and a symlink at its path is refused.
- Per-category coverage (head FYI after G16): a usage fixture without `content_references` still lets an absent dead-code id be fixed; drift without schema is not_checked.

### Gates

pytest 498 passed, 1 skipped after merging origin/main `7abc0ba` (S13 #84 on top of G16 #83; main alone 444 passed, 1 skipped; this slice adds 54); ruff check + format --check clean on src/ tests/ scripts/; mypy `src/strata_lookml --ignore-missing-imports` clean; `check_dashboard_js_syntax.py` and `gen_reference.py --check` pass (no CLI/MCP surface change). Fail-before: `tests/test_triage.py` against origin/main (detached worktree) errors at collection (no `strata_lookml.triage`). Negative controls, each mutation in a throwaway detached worktree failing at least one test: ack-wins-over-baseline, not_checked->fixed, rev check removed (2 fail), allowlist removed, TTL prune removed, re-ack keeps `unacked_at`, symlink read refusal removed, file mode 0644, hash-form link for `#` bases; the import guard fails on each of six planted imports (http, from-http, textual, jinja2, workbench, tui) placed one module down inside a function. Round 1 controls: lock never taken -> the race test fails (plus the three lock-seam tests); note validation removed -> both bad-note cases fail. Round 2 control: ack keeping the old absence stamp -> the retention test fails. Round 3 controls: the new tests against 629002d fail 6 (race, killed holder, dedicated lock, interrupted write, both interleave seams); `flock` not taken -> race + killed-holder tests fail; every category counted as run -> both not_checked tests fail.

## Date: 2026-11-08 — feat/wb-s13-diff (strata diff + run provenance, workbench S13)

Commit: 58b7373
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S13 of `workbench-spec-2026-11-08.md` (§6b Q3 dev vs prod, options A+B).
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the workbench spec (§6b), gate.py, pipeline.py, cli/{check,build_ir,main,_contract}.py, errors.py.
Exact Next Steps: twin gate, operator merges. On a main move, merge `origin/main`, hand-resolve, regenerate the reference, re-run the gates. Workbench/TUI can read `graph.metadata["source"]` and the `strata diff` JSON for a "new on this branch" filter.

### What changed

- `provenance.py`: `git_source(repo)` -> `{commit, branch, dirty}` (read-only `rev-parse`, `symbolic-ref`, `status --porcelain -- .`; branch "detached" on a detached HEAD; None outside git or without git). `resolve_commit` maps a ref via `rev-parse --verify <ref>^{commit}` (InvalidInput + hint on unknown; a leading-dash ref never reaches git). `materialised` exports a commit with `git archive | tarfile (filter="data")` into a system temp dir removed on exit.
- Provenance is stamped in `pipeline._repo_graph` into `graph.metadata["source"]` (and refreshed on a cache hit in `load_or_build`), and surfaced as an additive `source` key in `strata check --json` and `strata build` (text and JSON).
- Codex P1s fixed: every provenance/diff git call runs with `--no-optional-locks` + `GIT_OPTIONAL_LOCKS=0` (a plain `git status` rewrote `.git/index` after an mtime-only change; test asserts index bytes + mtime unchanged, fails on 97c2953). Snapshot orchestration and classification moved to `strata_lookml/diff.py` (`diff_findings(...) -> DiffResult`); the click command only parses, renders and sets the exit code.
- Export links: a committed symlink/hardlink pointing outside the project is skipped (the IR parser ignores such links anyway) instead of aborting the whole `git archive` extraction; other filter rejections (`..` paths, device files) still raise. `--untracked-files=normal` on the dirty check so `status.showUntrackedFiles=no` cannot hide untracked LookML.
- `strata diff <base> [<head>] [--usage-fixture] [--schema-fixture] [--fail-on-new] [--json]`: both sides analysed with the same fixtures, `finding_records` ids classified new / fixed / unchanged; `--json` `{base:{ref,commit}, head:{ref,commit[,dirty]}, new, fixed, unchanged_count}`. Head defaults to the working tree.

### Deviations from the brief

- `test_security`'s BigQuery test now fakes `subprocess` inside the `generate_schema` module only (a proxy namespace) instead of the global `subprocess.run`, so provenance's git calls are not intercepted; production code is not shaped around the fake.
- `test_check_json_is_stable` now drops the additive `source` key before its exact comparison (the fixture repo sits in a git checkout).
- Run from a project subdirectory, `git archive` exports that subtree only, so the temp copy is rooted at the project (no prefix handling needed).
- Working-tree head also reports `dirty`; the spec listed only `ref`/`commit`.

### Gates

pytest 434 passed, 1 skipped, ruff check + format --check clean, mypy `src/strata_lookml` clean, `docs/reference.md` regenerated by script. Negative control: `tests/test_diff.py` against origin/main code (detached throwaway worktree, PYTHONPATH to its `src`) fails 9 of 10; the only pass is the non-git "source omitted" case.

## Date: 2026-11-08 — fix/wb-g16-content-coverage (content coverage, workbench G16)

Commit: 5c5db7b
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: fix — G16 (S2 #82) of `workbench-spec-2026-11-08.md` §6b.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the workbench spec, l1/{enrich,provider,fixtures,replay,looker}.py, mcp/tools.py.
Exact Next Steps: twin gate, operator merges. On a main move, merge `origin/main`, hand-resolve, regenerate the reference, re-run the gates.

### What changed

- `analysis_coverage` gains `content`, read from `l1["content_checked"]` which `enrich_graph` writes as `content_references is not None`. Old caches lack the key and read as not checked.
- Providers say "not provided": `FixtureUsageProvider` returns None when `content_references` is absent, `ReplayUsageProvider` when `content_usage_rows` is absent; `UsageFacts.content_references` is `list | None`. The Looker provider's query always returns a list (ran, zero rows = checked).
- `strata_object`: `content` is null unless usage AND content were loaded; `coverage.content_checked` added. `strata_usage_summary` carries `content_checked`. Dashboard `COVERAGE` carries `content` additively.
- `_dead_code` unchanged: `content_keys` None-vs-empty already skipped the content leg; it now actually receives None for an absent section.

### Gates

pytest 428 passed, 1 skipped, ruff check + format --check clean, mypy `src/strata_lookml` clean, dashboard JS syntax check passes, reference regenerated by script. Golden: `strata check --json` byte-identical to origin/main (built_at filtered) for gcs_analytics and enterprise_mono. Negative control: the new `test_strata_object.py` cases on origin/main code (detached worktree, removed) fail 5 of 20 (KeyError on `content_checked`).

## Date: 2026-11-08 — feat/wb-s1-finding-records (finding record seam, workbench S1)

Commit: 5676289
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S1 of `workbench-spec-2026-11-08.md` (G4, G8, G14, D2; mockup items M1, M3).
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the workbench spec and validation report, gate.py, ir/source_lines.py, l1/{enrich,schema,types}.py, ir/resolver.py, tests/test_cli.py.
Exact Next Steps: twin gate, operator merges. S2 and S3 land serially; on a main move, merge `origin/main`, hand-resolve, regenerate the reference, re-run the gates.

### What changed

- `gate.finding_records(graph)`: one record per opt-in finding, `{category, id, message, label, subject_id, source_file, source_line, evidence_ids, cost_usd?}`. `findings_by_category` is now a projection (`{category, id, message}` rows, None where facts were not loaded) and `baseline_document` still projects ids from that, so there is one source of findings.
- Subjects: dead view -> `view:<name>`, dead explore -> its explore node, PDT -> `pdt:<view>`, missing_column -> the field node, missing_table -> `physical_table:<name>`. `cost_usd` only on PDT records.
- Labels (M3): dead-code and PDT drop the prefix; missing_column `<view.field> <- <table>.<col>` (project and dataset dropped); missing_table `<dataset>.<table>`. Full id stays the key.
- M1: `attach_source_lines` gives `pdt:<name>` the line of `view:<name>`.
- Integrity: `finding_records` leads with integrity records (label `subject: reason`); `findings_by_category` covers the opt-in categories only.
- Merged S2 (#82): `strata_object`'s per-category `_node_finding_ids` is replaced by a match on `finding_records` `subject_id` (a table also lists the column drift whose evidence names it). New test asserts every record lands on its subject node's `findings`.
- G14: duplicate ids yield multiple records, ids unchanged; the baseline de-duplicates.

### Deviations from the brief

- (Closed in review.) Integrity failures are records too (category `integrity`, the gate's ids); `_integrity_failures` projects from them. Resolution errors carry no node, file or line, so `subject_id`/`source_file`/`source_line` are None there; explore failures cite their explore node.
- `physical_table` nodes have no line, so a missing_table record cites ONE referencing node, a view (`view->physical_table`) or a PDT (`pdt->upstream`), first by (source_file, line, id), and takes both file and line from it (Codex P2: never mixed coordinates).
- G14 is not reachable from LookML: field ids are `view.field`, and a dotted-name pair collapses to one field node. The collision test injects a duplicate drift record into the L1 facts.

### Gates

pytest 424 passed, 1 skipped, ruff check + format --check clean, mypy `src/strata_lookml` clean. Golden: `strata check --fail-on all --json` and `--write-baseline` outputs byte-identical to origin/main for enterprise_mono, gcs_analytics and thelook (fixtures). Negative control: `tests/test_finding_records.py` on origin/main code (detached worktree) fails to import `finding_records`, and its PDT nodes have `source_line` None on all 5.

## Date: 2026-11-08 — feat/wb-s3-jinja (workbench S3: Jinja rendering foundation)

Commit: 905cee5
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S3 (D1, D6, §6a/§6b Q2 revised) of `workbench-spec-2026-11-08.md`.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D1, D6, S3, Q2), pyproject.toml, mcpb/, tests/test_security.py.
Exact Next Steps: twin gate, operator merges. S4b onward builds pages on `workbench.render.render()`; S10 retires `outputs/dashboard.py`.

### What changed

- New package `strata_lookml.workbench` (render.py, templates/_base.html, _smoke.html, _smoke.txt). One Environment factory: `PackageLoader`, `select_autoescape(default_for_string=True, default=True)` (escapes every extension), `StrictUndefined`, no extensions. `render(name, **ctx)`. `safe_svg()` is the only `Markup(` site.
- `jinja2>=3.1.3,<4` added to runtime dependencies (dbt-core's range; MarkupSafe comes with it). The wheel already packages all of `src/strata_lookml`, so templates ship; the mcpb shim pins `strata-lookml==` and needs no change. Dashboard untouched; L0 import guard green.
- `tests/test_workbench_render.py`: hostile-string escaping (text + attribute positions), StrictUndefined, autoescape on for .txt/unknown/string templates, static template scan (`|safe`, `autoescape false`, `Markup(`), AST scan for `Markup(` outside `safe_svg`, wheel contents + `Requires-Dist: jinja2`.

### Gates

pytest 400 passed, ruff check + format --check clean, mypy (CI invocation) clean, `docs/reference.md` regenerated with no diff. Negative controls (each planted, tests fail, then restored): `|safe` in the real template (5 fail incl. template scan); `Markup(` in a stray module (module scan fails); `autoescape=False` (5 fail); `default=False` (txt test fails); lax `Undefined` (2 fail); plus planted-violation tests for both scans.

## Date: 2026-11-08 — feat/wb-s2-strata-object (workbench S2: `strata_object`)

Commit: 73dbfcc
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S2 of `workbench-spec-2026-11-08.md` (D2, G3/G6, M5; operator Q5: yes, an MCP tool).
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, workbench spec + validation (M5), mcp/{tools,server}.py, cli/query.py, identifiers.py, l1/{enrich,types,schema}.py, gate.py.
Exact Next Steps: twin gate, operator merges. S1 (`finding_records`) and S3 land in parallel; once S1 merges, `_node_finding_ids` in `mcp/tools.py` should read `finding_records(...).subject_id` instead of matching per category.

### What changed

- `mcp/tools.strata_object(graph, kind, name)` for explore | view | pdt | table | field: `{kind, id, name, source_file, source_line, upstream, downstream, findings, coverage, content, details}`. Names resolve through `identifiers.py` (`model.explore`, `view.field`, table suffix); ambiguous -> InvalidInput with candidates, unknown -> NotFound.
- Reuse, not re-derivation: explore lineage from `strata_explore_deps`, table downstream from `strata_impact`, view/field downstream from `view_consumer_map`, PDT downstream from `direct_view_consumers`; findings are the ids of `gate.findings_by_category` records on the node (dead-code, PDT, drift).
- M5: explores carry `content` = `{reference_count, by_type, items, window, window_label}` from the existing L1 `content_references` / `evidence_facts` counts. The window is the usage period the facts were pulled for (`l1.period`, 30d in the fixtures), labelled "viewed in <days>d", not 90d and not all-time. `content` is null (never 0) when usage was not checked, and for non-explore kinds. Content items also appear as the explore's downstream.
- MCP tool `strata_object` (read-only, every parameter described) and CLI `strata query object KIND NAME` (JsonCommand). README tool counts (19 / 18 read-only) and table, `docs/reference.md` regenerated.
- `gate` is imported lazily inside `_node_finding_ids` (gate -> synthesis.slices -> mcp.tools would otherwise cycle).

### Deviations from the brief

- Window label is "viewed in 30d" (the data's real window), not the spec's "90d" — the fixtures and the Looker provider default to 30 days; the label is read from `l1.period`.
- PDT `source_line` is null until S1 (M1). Added a `details` key (kind-specific facts: explore joins/field count, field definition, PDT ledger record, view field count) beyond the brief's list.

### Gates

- [x] pytest 397 passed; ruff check; ruff format --check; mypy src/strata_lookml --ignore-missing-imports; docs/reference.md regenerated.
- [x] Fail-before: `tests/test_strata_object.py` against a detached worktree of origin/main errors at collection (no `strata_object`).

## Date: 2026-11-08 — fix/n9-model-scoped-explores (explores keyed by model, finding N9)

Commit: 4ad8164
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: patch — finding N9 of `ux-agentic-cli-docs-spec-2026-11-08.md` (context: D4, D13).
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§2 N9, D4, D13), ir/{parser,builder,resolver,types,store,source_lines}.py, identifiers.py, navigate.py, validation.py, mcp/tools.py, l1/{enrich,types}.py, synthesis/slices.py, outputs/{dashboard,pr_report,artifacts}.py, pipeline.py, tests/test_identifiers.py.
Exact Next Steps: twin gate, operator merges. S8 #78 is merged in (handoff hand-resolved, its block archived; reference regenerated, identical to main's). Last PR of the spec program.

### What changed

- Root cause was the resolver, not the ids: explore node ids were already `explore:<model>:<name>`, but `_collect_declarations` keyed explore definitions by name across all models, so a second model's same-named explore became a refinement of the first (one node, the second model's base view/joins, the first model's view orphaned).
- `ir/resolver._resolve_explores`: per-model namespaces. Layers, later wins: the one other model defining a name (cross-model `extends` base — thelook and enterprise_mono rely on it) < explores declared outside model files (shared, one model-less node as before) < the model's own. A model-file refinement of a name the model does not define goes to the shared explore if one exists; it never reaches another model's node. Errors de-duplicated across namespaces. Explores emitted by (name, model).
- One derivation: `ir.types.explore_id(model, name)` (`explore:<model>:<name>`) and `explore_key(model, name)` (`<model>.<name>`, the L1 fact key). Consumers routed: resolver, identifiers, navigate, validation, mcp/tools (`strata_explore_deps`, impact), synthesis/slices, l1/enrich (dead code, view consumers, evidence facts), l1/types (`ExploreUsage.key`, `ContentReference.explore_key`), outputs/dashboard (usage map, dead lookup, query count), outputs/pr_report. Not routed: the dashboard JS `exploreNodeIdFromKey` (JS-side mirror of the same rule; unchanged format) and `navigate._match_explores`, which parses ids.
- `ir/store.IR_FORMAT = 2`, recorded in `describe_inputs`; a cache written before it has no `ir_format`, so its inputs never match and it is rebuilt.
- Dashboard: graph nodes carry `display_label` = `model.explore` when another model has an explore of that name (else the bare name); the cytoscape label (`d.short`) uses it. `label` stays the bare name because the JS builds `model.label` fact keys from it.
- Fixture `tests/lookml/twin_models` (in-tree, not a submodule): `retail.orders` over `retail_orders`, `wholesale.orders` over `wholesale_orders` + a wholesale-only refinement joining `accounts`.

### Deviations from the brief

- Id scheme kept as `explore:<model>:<name>` rather than the suggested `explore:<model>.<explore>`: the existing ids were already model-scoped, every artifact/evidence id and dashboard anchor uses them, and `:` stays unambiguous where `.` is not (identifiers.py already handles explore names containing a dot). No id format changes; the only visible change is the label of a shared-name explore.
- Cross-model `extends` fallback kept (not real Looker semantics, but enterprise_mono's fixture uses it across 6+ models and `strata check` fails without it).

### Gates

pytest 381 passed after merging S8 #78 (369 before the merge; 365 on the original base; +5 in `tests/test_model_scoped_explores.py`, -1: the hand-built ambiguity test in test_identifiers.py is replaced by the real-LookML one), ruff check + format --check clean, mypy clean (CI invocation), dashboard JS syntax OK, `docs/reference.md` regenerated with no diff. Negative controls: the new tests against origin/main code (detached worktree, PYTHONPATH to its src) fail 5 of 5 (merged node with `wholesale_orders`; dead set `{view retail_orders}`; DID NOT RAISE InvalidInput; `only_b` leaked into model a; KeyError on the missing node). Mutations: dropping `ir_format` from `describe_inputs` fails the cache test (serves the merged graph); dropping the cross-model layer fails 4 existing tests (thelook/enterprise check + scenarios). `strata outputs` for gcs_analytics, thelook, enterprise_mono (the CI fixtures) is identical to origin/main's apart from timestamps (all 8 JSON artifacts; `strata outputs` writes no dashboard HTML); emitting by (name, model) is what keeps enterprise_mono's register order — per-model emission had reordered it.
Review (Artemis should_fix x2 + note, dashboard.py): the first cut put `model.explore` in `label`, and the JS builds `${model}.${label}` usage keys and tooltips from it, so a shared-name explore looked up `retail.retail.orders` and always read "no usage row". `label` is bare again; display goes through `display_label`. Test asserts both fields (fails on 794f563: KeyError display_label).
Review (Codex P1, resolver.py): the shared namespace resolved alone, so a shared explore extending a model-defined base lost the base's `from`/joins and reported `missing_extends_target`. The shared namespace now resolves through the same `resolve_scope` as a model's (model ""), with every uniquely-owned model explore as a fallback. Test `test_a_shared_explore_extends_a_model_defined_base` (fails on 794f563: `('derived', []) == ('orders', ['accounts'])`).
Review (Codex P2, resolver.py): each namespace resolved every fallback definition, so an unused fallback chain through an ambiguous base added a resolution error and failed integrity. `_resolve_named_objects(roots=)` resolves only the namespace's own explores and the ancestors they extend (cycle detection on that subgraph too). Test `test_an_unreached_ambiguous_fallback_adds_no_resolution_error` (fails on 794f563; also fails when `roots=` is dropped). Post-round: pytest 383 passed, ruff/format/mypy/JS syntax clean, reference unchanged, CI-fixture artifacts still identical to origin/main.

## Date: 2026-11-08 — feat/s8-mcp-validate (honest `mcp validate`, spec S8)

Commit: cccea71
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S8 (D8; finding B4) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the spec (B4, D8, S8), cli/mcp.py, config.load_cache_path, pipeline.build_graph, l1 fixture loaders, tests/test_cli.py.
Exact Next Steps: twin gate, operator merges. If another lane lands first, merge `origin/main`, hand-resolve handoff/CHANGELOG, re-run `python scripts/gen_reference.py`.

### What changed

- `cli/mcp.py` `mcp validate`: every check is pass (✓), warn (`~`, never affects exit) or fail (✗, exit 1). It builds the graph with `pipeline.build_graph` and reports node counts by kind, so "ready" means it parsed. Fails: repo missing, no `.lkml` files (the pipeline's `StrataError`), any other build crash, a configured `STRATA_USAGE_FIXTURE`/`STRATA_SCHEMA_FIXTURE` that is missing or does not load. Advisories: cache not built (hint: the server builds it on start; `strata build` pre-warms it — no mention of `strata outputs`), Looker token missing (only needed for `--looker-url`), fixture env unset (hint names `usage_checked=false` / `schema_checked=false`), BQ project unset. The cache path comes from `config.load_cache_path` (honours `STRATA_CACHE_PATH`).
- `--json` emits `{ready, checks: [{name, status, message, hint}], counts}`; exit code is the same.
- Tests: `tests/test_mcp_validate.py` (8, HOME in tmp); `tests/test_cli.py` assertions updated (`repo path: exists`; an empty dir now exits 1). README sample and regenerated `docs/reference.md`.
- Review (Codex P2, cli/mcp.py): validate only called the fixture loaders, so a fixture that loaded but broke enrichment read as ready. It now also runs `build_graph(repo, usage, schema)` (the server's startup path, no cache write) as a `fixture enrichment` check; any exception is a ✗. Upstream, `FixtureSchemaProvider` rejects non-string column entries / missing names with `InvalidInput` instead of a later TypeError in `enrich_schema_drift`. Tests fail on c523242 (4 of the 4 new). Fix commit cd0f86f.

### Deviations from the spec

- Fixtures are checked individually (one `usage facts`, one `schema facts` check) rather than one combined "no facts" advisory, so a half-configured setup names which one is missing.
- The "never mentions `strata outputs`" test already passed on origin/main (S7 had removed that remedy), so it guards against regression rather than proving a fix.

### Gates

pytest 373 passed, ruff check + format --check clean, mypy `src/strata_lookml` clean. Negative control: `tests/test_mcp_validate.py` run against origin/main code (detached worktree, `PYTHONPATH` on its `src`) fails 7 of 8; the passing one is the `strata outputs` guard.

## Date: 2026-11-08 — feat/s7-cache-location (IR cache location + identity, spec S7)

Commit: ce24f62
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S7 (D7; findings N1, N2; addendum from #70) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§2 N1/N2, D7, S7 + addendum), config.py, ir/store.py, pipeline.py, mcp/server.py, cli/{build_ir,mcp,main}.py, l1/looker.py (token dir helpers), security/deployment docs.
Exact Next Steps: twin gate, operator merges. S8 (`mcp validate` readiness) builds on `config.load_cache_path` and `ir.store.cache_age_seconds`/`cache_inputs`; it rewrites the cache line of `mcp validate` (S7 only routed it through the resolver). If S3/S5/#68 land first, merge `origin/main`, hand-resolve handoff/CHANGELOG, re-run `python scripts/gen_reference.py`.

### What changed

- `config.py`: `default_cache_path(repo)` = `~/.strata/cache/<repo-name>-<sha256(abs path)[:12]>.db`; `load_cache_path(repo, cache=None)` = `--cache` → `STRATA_CACHE_PATH` → default, the one resolver; `ensure_private_dir(dir, tighten=)` (missing levels created 0700; `tighten` chmods an existing Strata-owned dir). `l1/looker.prepare_token_dir` now creates through `ensure_private_dir` (refusal rule unchanged).
- `ir/store.py`: the cache row stores `inputs` (repo path + `lookml_fingerprint` — count, max `mtime_ns`, total size, hash of relative paths over `ir/parser.lkml_paths` — and fixture paths + `mtime_ns`, from `describe_inputs`); `save_ir` writes a 0600 temp file beside the target and `os.replace`s it (readers see the old or new cache, never half; an interrupted write leaves the old one), dir 0700 (tightens `~/.strata/cache`); readers (`cache_age_seconds`, `cache_inputs` via `_read_cache_column`) treat a missing table/column or a non-SQLite file as a miss, and `load_or_build` treats a failed `load_ir` after the freshness check as a miss; `cache_inputs`, `cache_is_fresh(path, inputs, max_age)`.
- `pipeline.py`: `build_and_cache` (inputs captured before the build) and `load_or_build` (reuse only when inputs match and age < max). The server's `load_configured_graph` and `strata build` go through them; the four path decisions (server `_cache_path`, build, `mcp validate`, `mcp config`) are gone.
- `strata build --cache` declares `STRATA_CACHE_PATH`. `strata clean` removes the repo's `~/.strata/cache` entry plus legacy `strata_ir.db` under the repo; `--repo` declares `STRATA_REPO_PATH` (addendum).
- Docs: security-hardening write table, enterprise-deployment, SECURITY.md, README (commands table + MCP layer note), cli-guide; regenerated `docs/reference.md`; CHANGELOG Changed with the compat note.

### Deviations from the spec

- `strata clean` deletes the default-location entry, not a cache at `STRATA_CACHE_PATH`/`--cache` (a user-chosen path is not Strata's to delete). Without `--repo`/env it cleans the cwd's entry.
- The N1 test asserts `usage_checked` (S2's field) rather than the spec's older `has_l1` wording.
- `ensure_private_dir` creates every missing level 0700, so a custom `--token-path` with missing parents now gets 0700 parents too (narrower than before).

### Gates

pytest 365 passed after merging S12 #77 (277 before S7; +18 in `tests/test_cache_location.py`, +23 from merging S3 #73, +12 from S5 #72, +16 from S10 #68, +1 from S11 #75), ruff check + format --check clean, mypy clean (CI invocation). Negative controls: the new tests against `origin/main` code (detached worktree) fail 6 of 7 — the server test fails `usage_checked False is True`; the passing one is the same-name-repos invariant of the new resolver. Mutations: `cache_is_fresh` ignoring inputs fails the N1 test; dropping the `.lkml` fingerprint from the inputs fails the lkml-edit test (`13 == 13 + 1`); dropping the 0600 create/chmod fails the mode test. Real `~/.strata` untouched by the suite (no `cache/` dir).

Review (head): the repo was keyed by path only, so a `.lkml` edit inside the reuse window served a stale IR. Inputs now carry a stat-only `.lkml` fingerprint over the parser's own discovery; `test_server_rebuilds_after_a_lkml_edit_within_the_reuse_window`.
Review (Codex P2, store.py): the drop/create/insert ran with DDL in autocommit, so a concurrent server start saw no `ir_cache` table and `cache_age_seconds` raised; a crash between the steps left a cache that never self-healed. Now temp file + `os.replace`, and damaged caches are a miss. Tests: `test_interrupted_cache_write_leaves_the_previous_cache_whole`, `test_server_rebuilds_a_damaged_cache_instead_of_failing[drop_table|not_a_database]` — all 3 fail on the previous head d40b07b (`assert None is not None`, `no such table: ir_cache`, `file is not a database`). `test_load_ir_open_cannot_create_…` now expects `cache_age_seconds` → None (miss) instead of a raise; its no-ghost-file invariant is unchanged.
Review (Codex P2, store.py:118, Windows): `os.replace` over a cache another process has open raises PermissionError, and `load_ir` left its connection open until GC. `load_ir` now closes via `contextlib.closing` (the other readers already closed in `_read_cache_column`); `save_ir` retries the replace 3 times with short backoff, then drops the temp file, keeps the old cache and emits a RuntimeWarning — the build/start still returns the fresh graph. Tests: `test_cache_swap_failure_keeps_old_cache_and_still_serves_the_new_graph`, `test_load_ir_closes_its_connection`; both fail on the previous head 85c8ac6 (PermissionError propagates; DID NOT RAISE ProgrammingError).
Review (Codex P1, store.py:149): `--cache`/`STRATA_CACHE_PATH` naming a `.lkml` file would be replaced by the SQLite cache (read-only breach). Same class as #72's `--write-baseline` P1, so the guard is now ONE helper, `safe_paths.check_write_destination(path, what=, is_ours=)` (symlink final component, `.lkml`/`.lookml`, directory, existing file not ours → `InvalidInput`), used by `gate.write_baseline` (its inline `_check_baseline_destination` deleted; `is_ours` = loads as a baseline; `strata check` maps `InvalidInput` to exit 2 as before) and `ir.store.save_ir` (`is_ours` = inside `~/.strata/cache`, or SQLite magic header). `load_cache_path` now uses abspath instead of resolve() so a symlinked `--cache` reaches the guard as a symlink. Consumers enumerated: gate.py, ir/store.py; chart writers keep their own sandbox guard (different contract: fixed dirs + O_NOFOLLOW). Tests: lkml / symlink / non-SQLite destinations refused with the file untouched (all 3 fail on d6e9fc7), existing Strata cache at a custom path replaced (positive control); #72's baseline destination tests pass unchanged; removing the `is_ours` check fails both the cache and baseline non-ours tests.
Merge of S9 (#76): `strata validate`'s `~/.strata/logs` now goes through the same `config.ensure_private_dir` (was a bare mkdir 0700) and the log name through `config.repo_key` — the `<name>-<sha256[:12]>` rule the cache path also uses, now derived in one place.
Review (Codex P1, store.py:114): outside `~/.strata/cache`, any SQLite file counted as ours, so `--cache` at a user's own database replaced it. `is_ours` there is now `ir.store.is_strata_cache`: SQLite header, opened `mode=ro` and closed, exactly one table `ir_cache` with the Strata columns (`id, built_at, payload` [+ `inputs`], so caches from earlier releases still count). `safe_paths.is_sqlite_file` deleted (no other consumer). Test: `test_build_refuses_to_overwrite_an_unrelated_sqlite_database` (fails on c4be02b; its `users` row survives); the custom-path replace and managed-dir damaged-cache tests still pass.

## Date: 2026-11-08 — feat/s12-port-fallback (dashboard port fallback, spec S12)

Commit: 8393a08
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S12 (D9; finding U11) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the spec (U11, D9, S12), cli/dashboard.py, tests/test_dashboard_host.py.
Exact Next Steps: twin gate on the PR, operator merges. Other wave lanes land serially; merge `origin/main`, hand-resolve handoff/CHANGELOG and regenerate `docs/reference.md`.

### What changed

- `cli/dashboard.py`: `bind_server` binds `127.0.0.1`. Without `--port` (click parameter source is DEFAULT, not a value comparison) and 8765 busy, it tries `FALLBACK_PORTS` (8766-8785) and the command prints the URL actually bound. An explicit `--port` that is busy raises `StrataError` (exit 1) naming the port; a fully busy range is a `StrataError` naming the range. Only `EADDRINUSE` triggers fallback; other `OSError`s propagate. `make_handler` gets the bound port, so the Host allow-list follows it.
- Dropped the `lsof ... | xargs kill -9` advice from `skills/governance/strata_workflow.md`; `docs/runbook.md`, `docs/security-hardening.md` and the regenerated `docs/reference.md` describe the fallback.
- Twin-gate fix: the dashboard server relied on EADDRINUSE, but `allow_reuse_address=True` lets a bind succeed on a port in use on Windows, so fallback would never trigger. The exclusive-bind server moved from `l1/oauth.py` into `strata_lookml/loopback.py` (`ExclusiveHTTPServer`), used by both the OAuth receiver and the dashboard; the dashboard no longer sets `socketserver.TCPServer.allow_reuse_address` globally.
- Codex P2: Windows reports an exclusive listener as WSAEACCES (errno EACCES / winerror 10013), not EADDRINUSE. `loopback.port_in_use(exc)` is the one predicate (EADDRINUSE; on win32 also EACCES/10013) used by `bind_server` for both fallback and the explicit-port error.

### Gates

pytest 339 passed (10 in `tests/test_dashboard_port.py`, on self-bound high ports; `DEFAULT_PORT`/`FALLBACK_PORTS` monkeypatched, never the real 8765), ruff check and format --check clean, mypy `src/strata_lookml` clean. Negative control: on a detached origin/main worktree the new tests error (no `DEFAULT_PORT`); mutating `make_handler(candidate)` to the requested port fails the allow-list test, and treating `--port` as never explicit fails both explicit-port tests.


## Date: 2026-11-08 — feat/s9-user-project (resolve the user's project; one conductor parser; hide lint, spec S9)

Commit: 511cf4c
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S9 (D10, D11; findings B8, U8, U9, N3) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the spec, cli/conductor.py, cli/validate.py, cli/lint.py, mcp/tools.py.
Exact Next Steps: twin gate on the PR, operator merges. Parallel lanes (S7, S11, S12) land serially; merge `origin/main`, hand-resolve handoff/CHANGELOG and regenerate `docs/reference.md`.

### What changed

- New `conductor_state.read_status`, used by `strata conductor status` and MCP `strata_conductor_status`. `active_slice` is line-anchored and null when absent or `none` (the old MCP regex captured prose). MCP now always returns all six keys (null when unknown).
- `validate`: project root is `--project-root`/`CONDUCTOR_PROJECT_ROOT`, else `load_repo_path()`; git checks run in that project; labels print the real relative path. `--check-replay` without `--replay` uses `<project>/tests/fixtures/replay_facts.json` only if present, else fails with "pass --replay".
- `lint` hidden (still invocable); removed from README and cli-guide. `generate-schema --repo` reads `STRATA_REPO_PATH`.

### Gates

pytest 335 passed, ruff check/format, mypy clean. Negative control (origin/main, new tests copied in): all 7 new tests fail.


## Date: 2026-11-08 — feat/s11-unknown-explores (explores "unknown" without usage facts, spec S11 / N7)

Commit: b6ee775
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: fix — spec S11 (finding N7) of `ux-agentic-cli-docs-spec-2026-11-08.md`; the KPI half of S11 was folded into #65.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the spec (N7, S11), outputs/AGENTS.md, outputs/dashboard.py, the node harness in tests/test_l1_synthesis_outputs.py.
Exact Next Steps: twin gate on the PR, operator merges.

### What changed

- `outputs/dashboard.py`: `NODE_PALETTE` gains `explore_unknown` (neutral grey, emitted as `--n-explore-unknown` like every other entry). `_build_graph_data` reads `analysis_coverage(graph)["usage"]` and stamps explore nodes `status` = `dead` / `active` / `unknown`; with no usage facts they take the unknown colour. The decision is serialized from coverage, not inferred in JS. The legend gains an "Unknown (no usage facts)" swatch and a note ("Usage facts not loaded — explore activity unknown") rendered visible only when usage is absent; the node badge reads UNKNOWN instead of KEEP. With usage loaded nothing changes.

### Gates

pytest 329 passed, ruff check and format --check clean, mypy clean, `scripts/check_dashboard_js_syntax.py` passes. Negative control: the new test run against a detached `origin/main` worktree fails (no `status` on explore nodes).


## Date: 2026-11-08 — feat/s10-chart-columns (chart column validation + --x/--y/--color, spec S10)

Commit: 6808e19
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S10 (D12; finding B6) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the spec (§1, B6, D12, S10), viz/render.py, cli/chart.py, mcp/tools.py, the four chart templates.
Exact Next Steps: twin gate on the PR, operator merges. Other wave-B lanes (S2, S4, S6) land serially; merge `origin/main`, hand-resolve handoff/CHANGELOG and regenerate `docs/reference.md`.

### What changed

- `viz/render.py`: `_check_encoding_columns` runs in `render_chart` (the one seam for `strata chart`, `strata-chart`, MCP `strata_render_chart` and `query navigate --chart`) after empty template channels are stripped. Every `encoding.*.field` must be a key in the union of row keys, else `InvalidInput` naming the missing and the available columns. The check covers single-view charts only: layered, composite (concat/facet/repeat/spec) and transform specs are passed to Vega unchecked, and `aggregate: count` / field `*` channels are skipped. Array channels (tooltip) are walked and Vega field paths (`a.b`, `a[0]`, `a\.b`) are parsed to their first component. Templates with `show_labels` are still checked (the check runs before they are layered). No rows means nothing to compare, so it passes.
- `cli/chart.py`: the four template commands are registered once by `_template_command`; each gains `--x/--y/--color`, which set the channel's field (adding the channel if the template lacks it). Help text lists the required columns and optional channels, read from the template YAML at import.
- README Charts section, CHANGELOG, regenerated `docs/reference.md`.

### Gates

pytest 328 passed (16 in `tests/test_chart_columns.py`), ruff check and format --check clean, mypy `src/strata_lookml` clean. Negative control: with the check replaced by `pass`, the CLI mismatch test and the MCP isError test fail; the override and help tests fail on main because the options do not exist.


## Date: 2026-11-08 — feat/s5-check-baseline (`strata check --baseline`, spec S5)

Commit: 4d71071
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S5 (D1 rest) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: small
Context Loaded: AGENTS.md, the spec (D1, S4, S5), gate.py, cli/check.py, tests/test_cli.py, README CI Gate.
Exact Next Steps: twin gate, operator merges. Merge `origin/main` when S3/S7/#68 land (hand-resolve handoff/CHANGELOG, `python scripts/gen_reference.py`).

### What changed

- `gate.py` owns the baseline: `write_baseline`/`baseline_document`, `load_baseline` (`BaselineError`), `findings_by_category` (was private), and `evaluate_gate(..., baseline=)` which subtracts known ids from the `--fail-on` categories before failing. `cli/check.py` only parses flags and formats.
- File format: JSON `{"version": 1, "findings": {category: [sorted unique ids]}}`, trailing newline; only categories whose facts were loaded are written.
- With `--baseline` the result adds `baselined` and `stale_baseline_ids` (stale = baselined id absent from a loaded category; a category not loaded this run is not judged). Without it the `--json` shape is unchanged.
- README CI Gate section (legacy-repo adoption), CHANGELOG Added, regenerated `docs/reference.md`.

### Deviations from the spec

- Ids are stored per category, not one flat list, so stale detection cannot misfire on a category whose fixture is not loaded in the checking run.
- `--write-baseline` also runs the gate afterwards (integrity failure still exits 1); it is mutually exclusive with `--baseline`.
- Unreadable/invalid baseline exits 2 via `click.UsageError` (a `StrataError` would exit 1 per the CLI contract).

### Gates

pytest 285 passed (+8 in `tests/test_cli.py`), ruff check + format --check clean, mypy clean (CI invocation), `gen_reference.py --check` clean. Negative controls: the new tests run against a detached `origin/main` worktree fail 8 of 8 (the bad-baseline cases assert our message names the file, so click's "no such option" cannot satisfy them).

Review round (Codex P1): `--write-baseline` could truncate a source file. `write_baseline` now resolves the destination and refuses (usage error, exit 2, before any write) a symlink final component, a `.lkml`/`.lookml` target, a directory, or an existing file that is not a prior Strata baseline; the write is temp-file-in-same-dir + `os.replace`. +4 tests (pytest 289); against the pre-fix code 3 of 4 fail (overwrite-a-previous-baseline is a guard that passes on both).


## Date: 2026-11-08 — feat/s3-identifiers (shared identifier resolution, spec S3)

Commit: 7c96545
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S3 (D4; findings U4, U5, U7) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§1, U4/U5/U7, D4, S3), mcp/{tools,server}.py, cli/query.py, validation.py, errors.py.
Exact Next Steps: twin gate, operator merges. S9 and S11 build on `identifiers.py`. Parallel lanes (S5, S7, #68): merge `origin/main`, hand-resolve handoff/CHANGELOG, regenerate `docs/reference.md`.

### What changed

- New `strata_lookml/identifiers.py`, the one resolver for `mcp/tools.py` and `cli/query.py`: `resolve_table` (exact or unique dot-boundary suffix; ambiguous -> `InvalidInput` listing candidates), `resolve_explore` (`model` optional, `model.explore` accepted), `resolve_field` (`view.field`), `parse_changed` (`kind:name`, `{kind,name}`, `.lkml` paths, bare name = view).
- `strata_impact` echoes the resolved `physical_table` plus `resolved_from` (the input when it differed, else null). `strata_explore_deps` echoes `model` and `explore`; `model` is optional on the tool and the CLI (`strata query explore EXPLORE [MODEL]`). `strata_query_field`/`strata query field` take `view.field` as one argument. Unknown model -> `NotFound` (explore_deps and view_sources).
- `validation.ChangedObject.from_value` delegates to `parse_changed`; the CLI's `_file_to_changed` is deleted and `strata query scope` passes its args straight through.
- Tool descriptions and CLI help updated; `docs/reference.md` regenerated.

### Deviations from the spec

- A bare name in `changed` is now a view (spec: "bare = view"), so the old `invalid_input` for `"bogus"` is gone; `tests/test_error_contract.py` now uses `"view:"` as the malformed example.
- `strata_explore_deps` ambiguity cannot arise from LookML today: the resolver keys explores by name across models, so two models sharing an explore name collapse to one node. The ambiguity path is implemented and tested against a hand-built graph; the collapse is a separate pre-existing limitation, not fixed here.

### Gates

pytest 300 passed (+23 in `tests/test_identifiers.py`), ruff check + format --check clean, mypy clean. Negative control: `tests/test_identifiers.py` against a detached worktree of origin/main fails 18 of 23 (the 5 passes are the unchanged positional forms and unknown-object errors).


## Date: 2026-11-08 — feat/s6-bootstrap (non-interactive, atomic bootstrap, spec S6)

Commit: 226be98
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S6 (D6; findings B2, U10) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§1, B2/U10, D6, S6), cli/{bootstrap,conductor,mcp,_contract}.py, errors.py, config.py, bootstrap templates, tests/test_cli.py.
Exact Next Steps: twin gate, operator merges. After S2 (U10 partial: MCP side of fixture env) and S4 land, merge `origin/main`, hand-resolve handoff/CHANGELOG, re-run `python scripts/gen_reference.py`. S7 (after S2+S6) and S9 build on `--yes` and `render_mcp_client_config`.

### What changed

- New `bootstrap/plan.py`: `FileOp` (write/mkdir/skip), `apply_plan` (temp file + `os.replace` per file; on any failure removes files and dirs created this run and restores overwritten bytes, then raises `StrataError`), `render_mcp_client_config(repo, usage, schema, client)` (the one renderer), `report_ops`.
- `cli/conductor.py`: `plan_conductor_init(target, force)` plain function; `conductor init` plans then applies. `cli/bootstrap.py` no longer uses CliRunner: gather inputs (`_gather_config`) → `plan_bootstrap` → apply. No tty and no `--yes` → `UsageError` (exit 2) before any write; `--dry-run` implies no prompts and prints the plan.
- Flags: `--yes/-y --bq-project --cost-threshold-gb --set-default-repo/--no-set-default-repo --usage-fixture --schema-fixture --dry-run`. Fixture paths must be existing files (exit 2). Fixture env goes into `.mcp.json` and `.cursor/mcp.json` (U10).
- `strata mcp config --client claude|cursor [--repo --usage-fixture --schema-fixture]` prints the bootstrap file byte-for-byte. The `mcp.json`/`cursor_mcp.json` templates are deleted (rendered in code).
- README Quick Start (`--yes`, submodule init for playgrounds), CHANGELOG, regenerated `docs/reference.md`.

### Deviations from the spec

- Rollback also restores files overwritten (`--force`, `.gitignore` append, existing config), not only files created; "created files removed" alone would leave a half-applied `--force` run.
- `--dry-run` skips prompts (it would be useless on a script otherwise). With `--yes`, existing config keeps its `repo_path` unless `--set-default-repo` is passed; flags still update bq_project/threshold, other keys are preserved (the old prompt path rewrote the file from scratch).

### Gates

pytest 239 passed (+8 in `tests/test_bootstrap.py`), ruff check + format --check clean, mypy clean (CI invocation). Negative controls: old `cli/bootstrap.py` against the new tests fails 7 of 8 (the conductor regression test is a guard that passes on both); disabling the rollback unlink fails both atomicity tests.

Review round (Codex): rollback now finishes even if a restore fails (successful replacements tracked separately, each undo step independent, one StrataError summarising failures); fixture options declare `envvar` + `show_envvar` on bootstrap and `mcp config --client` (also `--repo` there); `resolve_fixture` is the one path normaliser for both commands. Fix commit: d5bf6c2.
Round 3: rollback also runs on KeyboardInterrupt/BaseException (re-raised as is) and covers an in-flight replace that landed; writes go through symlinks to the resolved target (link untouched, rollback restores target bytes); `--repo` declares `STRATA_REPO_PATH` on `mcp config`, `conductor init/new-slice/status`. Not changed (outside this PR's files): `strata clean --repo`, `generate-schema --repo` still lack the envvar.
Round 4: rollback is one rule — snapshot each resolved destination (bytes + mode, or absent) before its first write, first snapshot wins, restore anything that differs through the same atomic writer (mode kept). Replaces the created/overwritten/in-flight bookkeeping.


## Date: 2026-11-08 — feat/s4-check-gate (`strata check` is a real CI gate, spec S4)

Commit: d86b7ac
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S4 (D1 minus baseline; finding B1) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§1, B1, D1, S4), cli/check.py, cli/_contract.py, errors.py, pipeline.py, l1/enrich.py, l1/schema.py, l1/types.py, ir/resolver.py, synthesis/verdicts.py, strata-ci.yml, strata-weekly.yml, README CI sections, docs check examples.
Exact Next Steps: twin gate on the PR, operator merges. Then S5 (`check --baseline` / `--write-baseline`): filter `gate.evaluate_gate`'s `failures` by `id` — every finding already carries a stable id (`dead:…`, `pdt:<view>`, `schema:…`, `resolution:<kind>:<type>:<subject>`, explore node id for verdict violations).

### What changed

- `strata_lookml/gate.py` (new API module): `evaluate_gate(graph, fail_on) -> {passed, failures, counts}` is the one gate decision; `cli/check.py` (argument parsing + output only, per `cli/AGENTS.md`) and `tests/test_scenarios.py` both call it. Codex P1 round 1 moved it out of the CLI layer. Integrity (resolution errors, verdict-evidence violations) always fails; missing repo / no `.lkml` already raise `StrataError` in `pipeline._repo_graph` (S1) and reach exit 1 through `StrataGroup`, with the `{error, code, hint}` envelope on stdout under `--json` (`JsonCommand`), so there is no second exit path. `--fail-on` (default `none`) adds `dead-code`, `unused-pdt`, `zombie-pdt`, `drift`, or `all`. Unknown category → `BadParameter` (exit 2); a category without its fixture → `UsageError` (exit 2), since it would otherwise pass by construction. `counts` has every category, `null` when its fixture was not loaded; failures sorted, JSON `sort_keys`.
- `tests/test_scenarios.py`: the old in-command assertions, parametrized over fixtures / gcs_analytics / thelook / enterprise_mono, each with the categories it must produce.
- CI: `strata-ci.yml` check steps renamed "(integrity gate)"; pytest now carries the scenarios. `strata-weekly.yml`: dropped the `gate: true` special case, `strata check` runs on every playground, plus `pytest tests/test_scenarios.py -k <name>`; checkout now uses `submodules: recursive`.
- Docs: README CI Gate + demo output + CI pipeline section, cli-guide, runbook, testing, CONTRIBUTING, the `strata_workflow` skill; `docs/reference.md` regenerated.

### Found on the way

- The weekly workflow checked out without submodules, so gcs_analytics and thelook were empty dirs there. That is the likely cause of the old comment's "sparse playgrounds don't reliably produce every signal" / "Py3.11 L1 emptiness bug"; locally on 3.14 both produce all their signals. Since S1 an empty dir fails with `no .lkml files`, so the weekly gcs/thelook jobs would have failed at `strata outputs` anyway. Fixed here with `submodules: recursive`; not verified on a 3.11 runner (the PR's CI runs 3.11 with submodules).

### Deviation from the spec

- None in behaviour. `--fail-on X` without X's fixture is a usage error; the spec does not say, and a silent pass was the alternative.

### Gates

pytest 241 passed (231 before; +6 in `tests/test_cli.py`, +4 in `tests/test_scenarios.py`), ruff check + format --check clean, mypy clean, `gen_reference.py --check` clean, dashboard JS check pass, the three CI `strata check` steps pass, `strata validate` 10 passed / 1 warning (handoff hash not reachable before this commit). Against the origin/main check.py all 6 CLI tests fail. Mutations, each failing its own test: resolution-error loop removed, fixture requirement removed, `fail_on` ignored (drift ids + JSON), default `all` (thelook default), lkml check removed in pipeline (empty dir), drift findings dropped (all 4 scenarios).


## Date: 2026-11-08 — feat/s2-mcp-envelope (MCP list envelope + agent descriptions, spec S2)

Commit: 315b540
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S2 (D3, D5; findings U1, U2, U10 partial, N6) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§1, U1/U2/U10/N6, D3, D5, S2), mcp/server.py, mcp/tools.py, l1/enrich.py `analysis_coverage`, tests/test_error_contract.py.
Exact Next Steps: twin gate on the PR, operator merges. If another wave-B lane lands first, merge `origin/main`, hand-resolve this log + CHANGELOG, re-run `python scripts/gen_reference.py`. S3 (identifier resolution) builds on this; S7 (cache identity) should keep `usage_checked`/`schema_checked` sourced from `analysis_coverage`.

### What changed

- `mcp/tools.py`: `list_envelope` / `l1_list_envelope` (the one `{"items","count"}` shape; L1 variant adds `usage_checked` or `schema_checked` plus a `hint` naming `STRATA_USAGE_FIXTURE` / `STRATA_SCHEMA_FIXTURE` when that check did not run). `strata_usage_summary` gains `usage_checked`, `schema_checked`, `hint` from `analysis_coverage()`; `has_l1` kept, documented deprecated (N6). `strata_find_field` takes `limit` (default 50, max 200, `InvalidInput` outside).
- `mcp/server.py`: the six list tools return the envelope; `MCPServer(..., instructions=...)`; every parameter is `Annotated[..., Field(description, examples)]`; tool descriptions state input format, failure modes, prerequisites; `find_field` `query` `min_length=2`; `render_chart` states the sandbox and column contract and keeps its destructive annotation. The semantic_layer_audit skill now checks `usage_checked`.
- The envelope is applied at the MCP seam only; the tool functions still return bare lists, so CLI output (`strata query orphans`, `strata skill`) is unchanged.
- `docs/reference.md` regenerated; CHANGELOG Unreleased/Changed "Breaking, MCP output shape".

### Deviations from the spec

- D3 says L1 tools add `has_l1` + hint; per the lane brief they add the specific `usage_checked` / `schema_checked` flag instead (`has_l1` only survives on `strata_usage_summary`, deprecated).
- `strata_render_chart` column contract is documented in its description, not enforced (enforcement is S10).

### Gates

pytest 249 passed (+18 in `tests/test_mcp_envelope.py`), ruff check + format --check clean, mypy clean. Negative control: with `src/` reverted to origin/main all 18 new tests fail, restored they pass. Tests run the real server through an in-process `mcp.Client` (mcp 2.3).


## Date: 2026-11-08 — feat/s1-error-contract (one error contract for MCP and CLI, spec S1)

Commit: d324871
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S1 (D2; findings B5, B7, U3, U6, U12) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§1, findings, D2, S1), mcp/tools.py, mcp/server.py, navigate.py, validation.py, pipeline.py, viz/render.py, cli/{main,query,auth,skill,build_ir}.py, the installed mcp 2.3.0 `mcpserver/exceptions.py` + `tools/base.py`.
Exact Next Steps: twin gate on the PR, operator merges. If S0 (generated reference) lands first, merge `origin/main` and re-run `python scripts/gen_reference.py`. Then wave B (S2 ∥ S4 ∥ S6 ∥ S10) builds on this contract: S2's unknown-skill-lists-names is already done here (the hint lists them); S4's `check` integrity failures should raise `StrataError` rather than add a second exit path.

### What changed

- `src/strata_lookml/errors.py`: `StrataError(ToolError)` (`mcp.server.mcpserver.exceptions.ToolError`, verified in the installed 2.3.0) with `NotFound` (`not_found`) and `InvalidInput` (`invalid_input`); fields `code`/`message`/`hint`; `str()` = `<message> Hint: <hint>`; `to_dict()` = the CLI JSON envelope.
- Raised from: `mcp/tools.py` (unknown field/explore/table/skill/model, bad orphan/find-field kind, render_chart path guard + YAML/JSON parse), `navigate.py` (no match), `validation.py` (bad `kind:name` / object), `pipeline._repo_graph` (missing repo, no `.lkml`; every pipeline entry point builds through it), `viz/render.py` (symlink guard, spec must be a mapping). `ir/parser.lkml_paths` is now the one .lkml discovery used by both `parse_repo` and the repo check. The duplicate repo check in `cli/build_ir.py` is gone.
- CLI seam `cli/_contract.py`: `StrataGroup` is the root group class (stderr `Error:`/`Hint:`, exit 1); `JsonCommand` on all `query` subcommands, `build`, `auth status` (stdout envelope; only with `--json` on commands that have that flag). No per-command try/except. `strata-chart` (argparse) has its one seam in `render.main`. `strata skill <unknown>` keeps exit 1, now through the seam.
- `auth status` without a token: `NotFound` with hint naming `strata auth login`; unsafe permissions → `InvalidInput` (message has the chmod).
- `pyproject` floor `mcp>=2.3,<3`. README "Error handling" (under CLI). Navigator skill text updated to the new failure shape. `scripts/test_mcp_live.py` catches `StrataError`.

### Deviation from the spec

- D2 has `errors.py` import the SDK's `ToolError`, but importing any `mcp.*` module runs `mcp/__init__`, which pulls httpx; `test_l0_no_network_imports` (pipeline is L0) failed with an eager import. `pipeline.py` therefore imports the error classes at raise time. Every other module imports them at the top. The L0 test is the negative control (eager import → it fails).

### Gates

pytest 229 passed (217 before; +12 in `tests/test_error_contract.py`), ruff check + format --check clean, mypy clean, dashboard JS check pass, the three CI `strata check` scenarios pass, `strata validate` 10 passed. All 12 new tests fail against the pre-change tree (origin/main 5ac4572). Seam mutations, each failing only its own test: StrataError base → Exception (5 MCP cases), StrataGroup catch removed (CLI envelope/hint), `as_json` gate removed (navigate human stdout), lkml check removed (empty repo), repo-dir check removed (`/nonexistent` → not_found), strata-chart catch removed, auth pre-check removed, view_sources model check removed, eager errors import in pipeline (L0 test).


## Date: 2026-11-08 — feat/s0-generated-reference (generated CLI/MCP reference + drift check, spec slice S0)

Commit: ac022ce
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <PR> --json mergeCommit`.
Conductor Mode: patch — docs/tests/scripts only; no runtime behaviour change.
Context Budget: low
Context Loaded: ux-agentic-cli-docs-spec-2026-11-08 (§1, D1/N4/N5, D14, S0), tests/test_docs_consistency.py, mcp/server.py, cli/main.py.
Exact Next Steps: operator reviews/merges; then S1 (spec) — D10 hides `lint`, which the generator and the N5 hidden-command filter already handle (rerun `python scripts/gen_reference.py` in that PR).

### What changed

- `scripts/gen_reference.py [--check]` writes `docs/reference.md` from the real click root group (every non-hidden command/subcommand: usage, options with envvars/defaults, first docstring paragraph) and the server's real `list_tools()` on an empty graph (name, title, description, parameters, annotations), plus derived counts. Deterministic: sorted, no timestamps, home dir rendered as `~`.
- `tests/test_docs_consistency.py`: `test_reference_is_current` (committed == generated), `test_readme_counts_match_introspection` (every `N tools` / `N analysis tools` / `N read-only` phrase), and the README CLI-table test now ignores hidden commands (N5). pytest already covers the check, so no separate CI step.
- `docs/cli-guide.md` summary table and the `mcp/AGENTS.md` signature list replaced with links to the reference (N4 drift removed).

### Gates

ruff check + format --check clean, mypy clean, pytest 219 passed. Negative control: editing the `auth logout` help string without regenerating fails `test_reference_is_current` and `gen_reference.py --check` (exit 1); regenerating passes; mutation reverted.


## Date: 2026-11-08 — feat/dashboard-polish (dashboard redesign: graph legibility + polish)

Commit: 630bbee
  (Implementation commit; the PR squash-merges. After the merge, resolve the landed anchor with `gh pr view <n> --json mergeCommit`.)
Conductor Mode: feature — dashboard presentation only; no artifact/schema change.
Context Budget: medium
Context Loaded: AGENTS.md, outputs/AGENTS.md, conductor/dashboard-north-star.md, handoff-log, dashboard.py, cli/dashboard.py, escaping guardrail + dashboard tests.
Exact Next Steps: operator approved the preview ("way better"); PR open on the twin gate, operator merges. Follow-ups are listed in the PR body (light theme, graph below the findings, phone card tables, whether the attention filter counts PDTs without build data).

### What changed

- Dependency graph: left-to-right layers (explores, views, PDTs/tables) with layer headers; short labels that fade below readable zoom and always show for the hovered/selected neighborhood; per-kind shapes (explore circle, view pill, PDT diamond, table barrel) and a halo on problem nodes; unconnected nodes laid out in their own row; canvas sized to the tallest layer; hover tooltip with the full name; search (name/model), per-kind toggles, a "Needs attention" filter, zoom-to-selection and reset; clickable upstream/downstream lists and a start-here list of problem nodes in the detail panel. Plain wheel scrolls the page; pinch or Cmd/Ctrl-wheel zooms (touch keeps native pinch).
- Single source for status colors: `NODE_PALETTE`/`EDGE_PALETTE` in dashboard.py are stamped onto nodes and emitted as `--n-*`/`--e-*` CSS tokens the legend, badges and PDT chart read. Tests now assert against the palette keys plus a distinctness check.
- New `attention` node flag (Python-side) drives the filter and start-here list. Note: in both fixtures every zombie/unused node is already `orphan`, so the status clause of the flag is belt-and-braces and not independently exercised by fixture data.
- Page polish: sticky section nav, data-driven headline naming the costliest problem, KPI cards ordered by severity and linking to their sections, sentence-case labels, sortable tables with sticky headers inside scroll containers, PDT ledger sorted by cost with palette-coloured chart, responsive to 390px (iframe-verified; headless Chrome cannot size a window below ~500px).
- Codex P2 on #65: without usage/schema facts the page claimed "This repo is clean." `l1.enrich.analysis_coverage(graph)` (one source, keyed on each enrichment step's own marker: `dead_code` / `schema_drift`) is embedded as `COVERAGE`; the headline, KPIs and empty states read it and say "not run" instead of clean/0. Headline/KPI wording lives in pure JS functions (`heroCopy`, `kpiCards`) that the test runs in node against real artifacts.
- Codex round 3 on #65: (a) spec B3/D13 folded in: `strata_usage_summary` serializes one explore population (`ir_explore_count`, `dead_explore_count`, `dead_view_count`, `active_explore_count` = ir − dead, `None` when usage unchecked); the KPI shows it instead of JS subtraction from usage rows (which went negative for unqueried explores). (b) a search/attention change clears a pinned selection; graph highlight state now lives in top-level `newGraphState`/`setGraphFilter`/`graphFilteredSet`/`applyGraphState`, tested in node against the vendored headless Cytoscape.
- `strata dashboard` serves dashboard.html at `/` (Host check still runs first; artifacts stay at their paths).

### Gates

ruff check + format --check clean, mypy clean, pytest 217 passed (209 before; +2 root-route host tests, +2 palette/attention tests, +2 coverage/not-run tests, +2 explore-population/pinned-filter tests), dashboard JS `node --check` pass. Negative controls: population test fails with the old JS subtraction, with a usage-row population, and pre-fix; pinned-filter test fails without the pin clear and pre-fix; not-run test fails with the clean-headline gate removed, with KPI coverage forced on, and against the pre-fix dashboard; root-route test fails with the rewrite removed; legend-token test fails with a hand-copied hex; attention test fails with the flag removed.


## Date: 2026-11-08 — docs/claims-match-code (docs match the code)

Commit: 17fa07b
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view 64 --json mergeCommit`.
Conductor Mode: patch — docs/help text only, no version bump.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log latest block, cli/mcp.py, cli/generate_schema.py, cli/validate.py, mcp/tools.py, docs/security-hardening.md, docs/enterprise-deployment.md, workflows.
Exact Next Steps: operator merges after the gate passes; no follow-up work.

### What changed

Four doc claims the code did not back, corrected without behavior change: (1) `strata mcp` help, GOVERNANCE.md and mcp/AGENTS.md said the MCP tools are all read-only; 17 are, `strata_render_chart` writes one HTML file under `~/.strata/output/` or `/tmp/` (path guard in mcp/tools.py). (2) security-hardening.md and enterprise-deployment.md listed Slack/Jira tokens as GitHub secrets; delivery is not implemented (scripts/notify.py) and no workflow references them, so the rows are removed. (3) enterprise-deployment.md called Conductor handoffs the audit trail; now described as a convention (`strata validate` only checks the `Commit:` hash exists). (4) generate-schema and its docs said ADC; the `bq` CLI uses gcloud's own credentials (`gcloud auth login`), per Google's BigQuery auth docs — help, the bq-missing hint, the dry-run hint, the schema script, cli-guide, two skills and README updated.

### Gates

Full pytest 205 passed (submodules initialized); ruff check, ruff format --check, mypy src clean. No test asserted the changed strings.


## Date: 2026-11-08 — fix/escaping-callback-scope (scope callback index vars)

Commit: cc9bb22
  (Implementation commit; the PR squash-merges, post-merge resolve the landed anchor with
  `gh pr view 63 --json mergeCommit`.)
Conductor Mode: patch — no version bump.
Context Budget: low
Context Loaded: AGENTS.md, conductor/AGENTS.md, handoff-log latest block, tests/test_l1_synthesis_outputs.py.
Exact Next Steps: operator merges after the gate passes; no follow-up work.

### What changed

Test-only. The escaping guardrail no longer trusts a `forEach/map` callback index block-wide; it is trusted only inside that callback's body (callback body spans, placeholders carry source offsets, `.map` bodies checked with the index added only for that body). Closes #31.

### Gates

New scoped/still-trusted tests; re-adding block-wide trust makes the scoped test fail. ruff check/format, mypy src clean; full pytest 183 passed (submodules initialized).


## Date: 2026-11-08 — fix/validate-active-slice (validate Active slice annotation)

Commit: 4db71ea
  (Implementation commit; the PR squash-merges, post-merge resolve the landed anchor with
  `gh pr view 62 --json mergeCommit`.)
Conductor Mode: patch — no version bump.
Context Budget: low
Context Loaded: AGENTS.md, conductor/AGENTS.md, handoff-log latest block, cli/validate.py, tests/test_cli.py.
Exact Next Steps: operator merges after the gate passes; no follow-up work.

### What changed

`get_active_slice_rel` in `cli/validate.py` used the whole remainder of the `Active slice:` line as the path, so index.md's annotation (`path.md (review — PR open; ...)`) failed the check. It now takes the first whitespace-delimited token (backticks stripped); the `none` sentinel and genuine missing-file failure are unchanged. `strata_conductor_status` still returns the full line as status text. Closes #47.

### Gates

New tests in tests/test_cli.py (plain, annotated, backticked, missing-file); with src reverted 3 fail. ruff check/format, mypy src clean; full pytest 185 passed (submodules initialized).


## Date: 2026-11-08 — fix/list-orphans-kind (narrow strata_list_orphans kind)

Commit: c17676f
  (Implementation commit; the PR squash-merges, post-merge resolve the landed anchor with
  `gh pr view 59 --json mergeCommit`.)
Conductor Mode: patch — no version bump.
Context Budget: low
Context Loaded: AGENTS.md, conductor/AGENTS.md, handoff-log latest block, mcp/tools.py, mcp/server.py, cli/query.py, README.
Exact Next Steps: operator merges after the gate passes; no follow-up work.

### What changed

`strata_list_orphans(kind=...)` accepted `explore|field` but only view orphans are recorded, so those kinds always returned `[]` (readable as "none exist"). Narrowed to `all|view`; other values raise `ValueError` with an explicit message. MCP tool schema (`Literal`), CLI `--kind` choice, and README table kept consistent. Closes #49.

### Gates

New `test_strata_list_orphans_rejects_unsupported_kind` fails with src reverted (3 failed), passes with the fix. ruff check/format, mypy src clean; full pytest 184 passed (submodules initialized).


## Date: 2026-11-08 — fix/chart-output-path (chart output: no fixed /tmp path, no symlink following)

Commit: 4afba41 (initial fix; review-round fixes follow it. The PR squash-merges; post-merge resolve
  the landed anchor with `gh pr view 61 --json mergeCommit`.)
Conductor Mode: patch — security hardening, no new tool or layer change.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, viz/render.py, cli/chart.py, mcp/tools.py, l1/looker.py
  (the #58 O_NOFOLLOW pattern), docs/security-hardening.md.
Exact Next Steps: operator merges after twins/Codex pass; CHANGELOG Unreleased > Security rides the
  next tag.

### What changed

- `render_chart(out_path=None)` defaults to a fresh `mkstemp("strata_chart_*.html")`; explicit
  paths are opened with `O_NOFOLLOW` (`_write_html`). Where `O_NOFOLLOW` is absent, an lstat
  (`is_symlink`) check refuses a symlink instead.
- `strata chart` / `strata-chart` `--out` no longer defaults to `/tmp/strata_chart.html`.
- MCP `strata_render_chart` resolves only the parent dir and refuses a final-component symlink
  before the root check, so confinement does not depend on `O_NOFOLLOW`.
- `strata query navigate --chart` goes through `strata_render_chart`, so it is covered.

### Verification

- New tests in `tests/test_security.py` (fresh default, normal write, symlink refused in
  render_chart + MCP, symlink refused with `O_NOFOLLOW` monkeypatched away). Reverting `src/`
  makes the behavior tests fail; restored, all pass.
- Full suite 186 passed (with test submodules initialised), ruff, ruff format, mypy clean.


## Date: 2026-11-08 — fix/dashboard-host-check (DNS-rebinding guard on `strata dashboard`)

Commit: e73ccd9 (first implementation commit; review-fix commits follow. The PR squash-merges;
  resolve the landed anchor with `gh pr view 60 --json mergeCommit`.)
Conductor Mode: patch — one security fix, no new tool, no layer-boundary change.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, cli/dashboard.py, docs/security-hardening.md.
Exact Next Steps: operator merges after the gates pass; the fix rides the next release.

### What changed

- `cli/dashboard.py`: `allowed_hosts(port)` / `make_handler(port)`. The handler answers 403 (no
  artifact content) unless `Host` is `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>`
  (case-insensitive); on port 80 the port-less forms are also accepted, since browsers omit the
  default port. Allowlist only; enforced in `send_head` (GET + HEAD).
- `tests/test_dashboard_host.py`: loopback forms served; foreign, wrong-port, port-less, empty and
  missing Host refused; port-less accepted only for port 80.
- `CHANGELOG.md` (Unreleased > Security), `docs/security-hardening.md` (Network Surface).

### Verification

- Negative control: with the allowlist check disabled, the refusal tests fail (7 of the first 11).
- Gates (with submodules initialized): pytest, ruff check, ruff format --check, mypy src.


## Date: 2026-11-04 — fix/security-0.1.9 (security hardening before the 0.1.9 tag)

Commit: 39be7b8 (the fix commit; the docs commit and any review fixes follow it. The PR squash-merges; post-merge resolve
  the landed anchor with `gh pr view <this PR> --json mergeCommit`.)
Conductor Mode: patch — security fixes from a read-only audit at origin/main 9d19e42, plus the
  docs that describe them. No new MCP tool, no layer-boundary change.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, generate_schema.py + scripts/generate_schema_facts.py,
  l1/looker.py, cli/auth.py, cli/mcp.py, mcp/server.py + ir/store.py, viz/render.py,
  mcp/tools.py, cli/dashboard.py, ir/parser.py, SECURITY.md, docs/security-hardening.md,
  docs/enterprise-deployment.md, README security sections.
Grounding: Looker OAuth guide https://docs.cloud.google.com/looker/docs/api-cors (auth on the UI
  host with client_id/state/S256 challenge; JSON POST to /api/token on the API host; redirect
  URIs matched exactly; registration via Admin or register_oauth_client_app with group_id; no
  refresh request documented). bq `--parameter` ARRAY syntax and the identifier limitation:
  https://docs.cloud.google.com/bigquery/docs/parameterized-queries. `--max_rows` default 100 and
  `--maximum_bytes_billed`: https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference.
Exact Next Steps: operator merges after twins pass -> tag v0.1.9 per the previous handoff (now in
  handoff-archive.md). First real Looker login is the live validation of the OAuth flow; until
  then the docs label it "not yet validated against a live instance".

### What changed

- generate-schema: one source for query construction (`build_columns_query`), shared by the CLI
  and the script; identifier allowlist; table names as `@names` ARRAY parameter; bytes/rows caps.
- Looker OAuth: new `l1/oauth.py` (PKCE, state, `code_from_callback`, `LoopbackReceiver`);
  `auth login` loses `--code`, gains `--api-url`, `--client-id` (alias `--client-guid`),
  `--timeout`; `--no-browser` = paste-on-stdin.
- Token: `LookerToken.ensure_usable_for` is the single origin+expiry check, run at runner
  construction and per request; redirects refused via a no-redirect opener; refresh token not
  stored; atomic 0600 write, 0700 dir; loose perms refused.
- D-1..D-4 local hardening (cache age, stdout in MCP, .html, 127.0.0.1 bind, symlink skip).

### Design calls (conservative options taken)

- Fixed loopback port 48765, not ephemeral: Looker matches registered redirect URIs exactly.
  BREAKING for anyone who registered the old 8765 URI; CHANGELOG says so.
- Refresh token dropped rather than stored unused (no documented refresh grant).
- Token directory: create missing dirs 0700 and keep `~/.strata` 0700, but never chmod any other
  existing directory — a custom `--token-path` in a group/other-accessible directory is refused,
  checked before the browser opens (a code is single-use).
- `--max_rows` raised to 1,000,000: the bq default of 100 truncated column inventories — a
  pre-existing correctness bug fixed in passing because the argv was being rebuilt anyway.

### Pre-gate (local Artemis, FIX-FIRST, no blocker) — dispositions

- Fixed: loopback handler socket timeout (idle connection stalled `--timeout`); stray/forged-state
  callbacks now get 400 and the login keeps waiting; non-ASCII `state` compared as bytes;
  exclusive bind on Windows (`SO_EXCLUSIVEADDRUSE`, no `SO_REUSEADDR`; POSIX keeps
  `SO_REUSEADDR` so a retry can rebind during TIME_WAIT — Codex P2 on PR #58); token-dir rule above; origin-binding
  error names the API URL to pass; `outputs`/`dashboard` map token/API refusals to CLI errors via
  one helper (`cli/outputs.py:live_looker_graph`); docs' write table completed (build, chart,
  query navigate, conductor, validate log, clean deletions) and listener wording made exact.
- Filed as pre-existing (not this PR): dashboard Host-header / DNS-rebinding; `/tmp` chart writes
  follow symlinks.

### Gates

Final tree (head of this branch; also in the PR body):
  ruff check src/ tests/ scripts/ -> "All checks passed!"
  ruff format --check src/ tests/ scripts/ -> "176 files already formatted"
  mypy src/strata_lookml --ignore-missing-imports -> "Success: no issues found in 88 source files"
  python -m pytest -> "181 passed" (157 before this branch)
  python scripts/check_dashboard_js_syntax.py -> "5 generated <script> block(s) passed node --check"
Negative controls: every security guard reverted one at a time -> its test fails (18/18, plus
  the POSIX reuse-address and localhost-refusal controls added in review).
CI round 2 (e701a84): Artemis SHIP (one should_fix: `localhost` redirect vs IPv4-only listener ->
  fixed, receiver now accepts only 127.0.0.1); Apollo ACCEPT (note: gate lines not visible to it
  -> now inlined here); Codex P2 (POSIX SO_REUSEADDR) fixed + resolved.


## Date: 2026-11-04 — docs/legal-0.1.9 (legal-readiness docs + shipped third-party notices)

Commit: e6da3ab (implementation commit; the PR squash-merges, resolve the landed anchor with
  `gh pr view 55 --json mergeCommit`.)
Conductor Mode: patch — docs + packaging metadata only, no src/ Python change, no version bump.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log latest block, pyproject.toml, README.md, CONTRIBUTING.md,
  docs/testing.md, docs/testing-findings.md, docs/runbook.md, src/strata_lookml/assets/js/.
Context Skipped: slices; src/ Python.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: unchanged — v0.1.9 is tagged only after the security-hardening PR also lands.
Changes: THIRD_PARTY_LICENSES (repo root + src/strata_lookml/assets/, so it ships in the wheel;
  `/THIRD_PARTY_LICENSES` added to the sdist include) covering the 7 vendored JS bundles plus
  graphlib/lodash inside dagre; README non-affiliation disclaimer + AI-assistance line;
  "synthetic demo fixture" labels on dollar figures (README, docs, skills); fixture provenance
  (thelook = fork of the archived, unlicensed looker-open-source/thelook, test-only, not shipped);
  CONTRIBUTING licensing of contributions (Apache-2.0 inbound=outbound, DCO sign-off).
Exact Next Steps: merge; after the security PR lands, tag v0.1.9 and confirm the built wheel and
  sdist on PyPI contain THIRD_PARTY_LICENSES. Open follow-up: the Vega bundles' smaller
  permissive sub-components (d3-*, vega-themes, vega-tooltip, semver) are noted, not enumerated.

### Gates

`python -m build` OK — wheel has strata_lookml/assets/THIRD_PARTY_LICENSES, sdist has both
copies and no tests/ fixtures; tests/test_docs_consistency.py 5 passed; README fences balanced;
PR CI (test, pr-analysis, review) green.


## Date: 2026-11-04 — ci/release-mcp-registry-oidc (MCP Registry publish in release.yml)

Commit: eb8ebee (implementation commit; the PR squash-merges, resolve the landed anchor with
  `gh pr view <this PR> --json mergeCommit`.)
Conductor Mode: patch — CI only, no src/ change, no version bump.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log latest block, .github/workflows/release.yml,
  .github/WORKFLOWS.md, the registry's github-actions.mdx.
Context Skipped: slices; src/.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: unchanged — the v0.1.9 tag push now also runs `publish-mcp-registry`
  (needs publish-pypi; OIDC login, mcp-publisher v1.8.7 pinned + cosign-verified).
Exact Next Steps: merge, tag v0.1.9 as already planned, then verify the registry listing for
  `io.github.G-Schumacher44/strata-oss` (registry search or API) instead of running
  `mcp-publisher` by hand. The OIDC publish is only exercised by the real tag run; if it fails
  after PyPI is live, fix forward and re-run the failed job.

### Gates

actionlint on release.yml clean; YAML parse OK; PR CI (test, pr-analysis, review) green.


## Date: 2026-11-03 — chore/release-0.1.9 (version bump, stacked on #46)

Commit: 553889b (the bump commit, on top of #46 head de7af40; review P3 fixes follow it.
  The PR squash-merges; post-merge resolve the landed anchor with `gh pr view <this PR> --json
  mergeCommit`.)
Conductor Mode: patch — version bump + release-guard hardening, no new slice.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log latest block, CHANGELOG.md, pyproject.toml, mcpb/
  {manifest.json,pyproject.toml}, server.json, .github/workflows/release.yml, the #44/#45/#46/#50
  handoffs.
Context Skipped: slices; src/ (no code change).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: RELEASE TRIGGER — after this merges to main, the operator tags `v0.1.9`; the tag
  push runs release.yml (guard -> build -> PyPI -> GitHub Release with the .mcpb).
Exact Next Steps: merge order #45 -> retarget #46 to main, merge -> retarget this PR to main,
  merge -> `git tag v0.1.9 <merge sha> && git push origin v0.1.9` -> verify PyPI 0.1.9 + the
  Release -> registry publish is now automated in release.yml (see the 2026-11-04 block).

### What changed

- 0.1.9 in all five version fields: pyproject `version`, mcpb/manifest.json `version`,
  mcpb/pyproject.toml (shim `version` and the `strata-lookml==0.1.9` pin), server.json top-level
  `version` and `packages[0].version`.
- CHANGELOG: `## [0.1.9] - 2026-11-03` cut from Unreleased (date = PR day; adjust on tag day if
  the tag slips), adding #44 (server.json, mcp-name token, `strata-lookml` script, titles +
  ToolAnnotations) and the ten #50 fixes beside the rename (BREAKING for importers, with the
  `--force-reinstall --no-deps strata` repair) and #46's items. Compare links updated.
- release.yml guard now also checks server.json (top-level and every `packages[].version`, and
  fails when `packages` is empty), so the four version files cannot drift. Still fail-closed: a
  missing file or key raises and exits non-zero under `set -euo pipefail`.

### Gates

Final tree: ruff check "All checks passed!", ruff format --check "211 files already formatted",
  mypy src "Success: no issues found in 87 source files", pytest -q "157 passed" (no new tests;
  the existing registry-manifest test already pins server.json == pyproject version).
Release guard, extracted verbatim from release.yml and run locally: `GITHUB_REF_NAME=v0.1.9`
  -> "tag v0.1.9 matches pyproject, manifest, shim pin, and server.json", exit 0;
  `v0.1.10` -> "VERSION MISMATCH — refusing to publish:" with all five fields listed, exit 1.
  Negative controls on the new leg alone: server.json `packages[0].version` drifted to 0.1.8 ->
  exit 1 naming only that field; `packages: []` -> "server.json has no packages entry", exit 1.
Build: sdist + wheel `strata_lookml-0.1.9`; installed beside `strata==26.0.0`, MCP initialize
  reports serverInfo version 0.1.9, tools/list = 18 (18 titles, 18 annotations, 18 descriptions).


## Date: 2026-11-03 — chore/release-0.1.9-readiness (PR #46, stacked on #45)

Commit: 2aa93bc (last of the six implementation commits; review fixes b6559cc and 027efe1 on
  top, then merges of refactor/import-strata-lookml carrying #44 + the #50 batch. The PR
  squash-merges; post-merge resolve the landed anchor with `gh pr view 46 --json mergeCommit`.)
Conductor Mode: patch — six small, independent changes, one commit each. None changes a layer
  boundary, adds a tool, or alters a tool's behavior (descriptions, `--help`, an escape inside a
  JS comment). Codex asked for Full Conductor; recorded as a judgment call on the PR thread.
Context Budget: medium
Context Loaded: AGENTS.md, conductor/index.md, README.md, pyproject.toml, .github/workflows/*,
  src/strata_lookml/mcp/{server,tools}.py, ir/resolver.py (_mark_orphans), l1/{enrich,schema}.py,
  outputs/dashboard.py, the #44 diff, `gh release view` v0.1.6-v0.1.8.
Context Skipped: slice specs; handoff-archive beyond prepending #45's block.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump here — 0.1.9 rides the stacked `chore/release-0.1.9` PR.
Exact Next Steps: after #45 merges, retarget this PR to main and merge it; then retarget and merge
  the 0.1.9 bump PR and tag v0.1.9.

### What changed

1. README for PyPI: every relative link is an absolute `github.com/.../blob/main/` URL; Quick
   Start opens with `pipx install strata-lookml` (editable install moved to clone-and-try); the
   naming note is corrected (`strata-mcp` 1.0.2 installs a `strata` command, `strata` 26.0.0 has
   no entry points, both ship a top-level `strata/`) and carries the 0.1.8 upgrade repair; PyPI
   strips the badge deep-link schemes; a no-credentials path for your own repo (`query status`,
   `query orphans`, `outputs`).
2. pyproject: PEP 639 SPDX `license` + `license-files` (License classifier dropped),
   `hatchling>=1.27`, keywords, extra classifiers, Documentation/Changelog URLs. No 3.14
   classifier (CI tests only 3.11).
3. CHANGELOG.md (Keep a Changelog): 0.1.6-0.1.8 from the release notes, plus Unreleased.
4. Descriptions for the 8 MCP tools that had none (docstrings only). After the merge every tool
   keeps #44's `title` + `ToolAnnotations` AND has a description; a registry test fails if any
   tool lacks one.
5. `outputs/dashboard.py`: the invalid `\]` escape in a JS comment is now `\\]`; the generated
   template is byte-identical. A test compiles every module with Syntax/DeprecationWarning
   promoted to errors.
6. `strata-mcp --help`/`-h` prints usage and exits 0 without building the graph or opening stdio.

### Not done on purpose

- No version bump (separate stacked PR, after #44's server.json landed).
- No PEP 794 `import-names` field (core metadata 2.5; PyPI/twine support unverified).

### Merge of the updated #45 (#44 + #50 on main)

- Auto-merged with no textual conflicts: #44's decorator lines (`title=`, `annotations=`) and
  #46's docstrings touch different lines of `mcp/server.py`; README and pyproject merged cleanly
  because #45 had already absorbed #44's hunks.
- Handoffs: the per-branch `conductor/handoff/chore-release-0.1.9-readiness.md` is replaced by
  this block; #45's block moved to handoff-archive.md.

### Gates

Final tree (after merging the updated #45): ruff check "All checks passed!", ruff format --check
  "211 files already formatted", mypy src "Success: no issues found in 87 source files", pytest -q
  "157 passed" (154 on #45 + 3 from this PR).
Wheel re-proof beside `strata==26.0.0`: 0 entries under `strata/`, 166 under `strata_lookml/`; all
  four `--help` exit 0 (`strata-mcp --help` prints usage); MCP stdio tools/list = 18 tools, 18 with
  title, 18 with annotations, 18 with a description.


## Date: 2026-11-03 — refactor/import-strata-lookml (PR #45, import rename strata -> strata_lookml)

Commit: 55f4ded (the rename; follow-ups 7d63fa1 mcpb shim, 29a9c5d, 75d5bae upgrade-path note,
  then a merge of origin/main 63cab83 carrying #44 + the #50 batch across the rename. The PR
  squash-merges; post-merge resolve the landed anchor with `gh pr view 45 --json mergeCommit`.)
Conductor Mode: patch — a mechanical, repo-wide rename with no behavior change and no new slice.
Context Budget: medium
Context Loaded: AGENTS.md, conductor/index.md, handoff-log latest block, pyproject.toml,
  .github/workflows/*, mcpb/*, server.json, every file referencing the old package path, and the
  #44/#50 diffs merged in from main.
Context Skipped: slice specs; historical handoff blocks (records of past work keep `src/strata`).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump here — 0.1.9 rides `chore/release-0.1.9` (stacked on #46).
Exact Next Steps: merge #45, retarget #46 to main and merge it, retarget and merge the 0.1.9 bump
  PR, then tag v0.1.9.

### What changed

- `git mv src/strata src/strata_lookml`. The import package `strata` collided with the unrelated
  PyPI project `strata` (26.0.0 ships `strata/__init__.py` and `strata/config.py`); installing
  both in one environment overwrote files.
- Every importer rewritten (src, tests, scripts, mcpb shim, `-m strata.cli.main` subprocess calls,
  the L0 offline-import probe, `src/strata/...` paths in pyproject, CI, GOVERNANCE.md, AGENTS.md,
  docs, README). No `strata` compatibility shim (it would recreate the collision).
- `[project.scripts]` targets moved to `strata_lookml.*`; the names `strata`, `strata-mcp`,
  `strata-chart` and #44's `strata-lookml` are unchanged.
- schema-refresh skill: `python -m strata --help` (never worked, no `__main__`) is now
  `.venv/bin/strata --help`.
- mcpb shim resolves the installed distribution's `strata-mcp` console-script entry point instead
  of importing a module path, so it works against both the 0.1.8 pin and the renamed package
  (Codex P2 on #45).
- Not changed on purpose: the `client_guid=com.gsanalytics.strata.cli` OAuth identifier, the MCP
  server name `strata`, the `.mcp.json` key, `~/.strata/` paths, historical conductor docs.

### Merge of origin/main (#44 + #50 batch)

- Git's rename detection carried every #44/#50 hunk to `src/strata_lookml/`; nothing landed at
  the old path. Five textual conflicts (pyproject scripts, cli/query.py, l1/looker.py,
  tests/test_ir_resolver.py, tests/test_mcp_tools.py) were all new import lines: resolved to
  main's content with `strata.` rewritten to `strata_lookml.`. #44's `strata-lookml` script
  targets `strata_lookml.mcp.server:main`.
- New `from strata...` lines main added in non-conflicting hunks (tests/test_cli.py,
  test_l1_providers.py, test_mcp_tools.py, test_security.py) rewritten by hand; one stale
  comment in cli/skill.py too.
- Handoffs: this repo keeps ONLY handoff-log.md. #45's per-branch file is replaced by this block;
  #44's `conductor/handoff/feat-registry-readiness.md` is folded into handoff-archive.md and
  deleted; the #50 batch block moved to the archive.

### Upgrade path (Codex P2 on #45)

Upgrading 0.1.8 -> the renamed release in an env that also has PyPI `strata` (or `strata-mcp`)
removes the shared `strata/__init__.py` and `strata/config.py` via 0.1.8's RECORD. Repaired by
`pip install --force-reinstall --no-deps strata`. The README naming note carries it; the 0.1.9
CHANGELOG entry carries it too.

### Gates

Final tree after the origin/main merge (706d1ed): ruff check "All checks passed!", ruff format
  --check "210 files already formatted", mypy src "Success: no issues found in 87 source files",
  pytest -q "154 passed" (132 on the pre-merge branch; the rename adds no tests).
Wheel re-proof: 0 entries under `strata/`, 166 under `strata_lookml/`; installed in a fresh venv
  beside `strata==26.0.0`: both import, `strata`/`strata-chart`/`strata-lookml`/`strata-mcp --help`
  exit 0, MCP stdio initialize + tools/list = 18 tools via strata-mcp, strata-lookml and the mcpb
  shim. Local twins: Apollo PASS, Artemis PASS (two P3s fixed: live starter-prompt template paths,
  this gate block).


## Date: 2026-11-03 — fix/batch-2026-11 (batch of ten correctness fixes)

Commit: 669e188 (last code commit on the PR branch, pre-merge anchor. This PR is meant to be
  REBASE-merged so the per-fix commits stay reviewable; rebase rewrites SHAs, so post-merge
  resolve the landed anchor with `git log --grep "one table-ref unquoting rule" origin/main`.)
Conductor Mode: patch — ten independent bug fixes batched into one PR, plus fixes for the
  unresolved Codex findings on their source PRs; no new slice.
Context Budget: medium
Context Loaded: AGENTS.md, conductor/AGENTS.md, conductor/CONDUCTOR_MODES.md, handoff-log latest
  block, source PRs #33 #35-#43 (diffs + unresolved review threads), src/strata/cli/{main,
  query,dashboard,outputs,conductor}.py, navigate.py, ir/{store,resolver,source_lines}.py,
  l1/{replay,looker}.py, viz/render.py, mcp/tools.py.
Context Skipped: handoff-archive.md beyond prepending the previous block; slices.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump — fixes only, no release trigger.
Exact Next Steps: review and rebase-merge the batch PR, then close #33 and #35-#43 as
  superseded; next, reconcile the two handoff-log readers (`strata conductor status` splits on
  "##" while strata_conductor_status only reads "## Date:" headers) — file an issue for it (the batch agent was not permitted to).

### What landed (one commit per source PR, handoff files dropped)

- #33 backtick-quoted BigQuery tables in PDT upstream SQL (Bug Hunt draft, reviewed fresh).
- #35 `<` escaped in chart HTML so data cannot close the script block.
- #36 navigate chart spec built as data (JSON), not an f-string YAML template.
- #37 `strata clean` sweeps `__pycache__` under `--repo`, not the cwd.
- #38 `dataset.table` anchors classify as physical tables when the IR has them.
- #39 `load_ir` raises FileNotFoundError instead of creating a ghost cache file.
- #40 ISO timestamps compared as instants; one shared `_latest_iso`.
- #41 source-line scan cache cleared on every build.
- #42 navigate chart written under the guarded output root (`~/.strata/output`).
- #43 DROPPED (see below).

### Review findings resolved (each its own commit with a test that fails without it)

- #36 `</script>` anchor in the chart: #35's escaping already neutralizes it once both land;
  pinned end-to-end by `test_navigate_chart_anchor_cannot_break_out_of_the_script_block`.
- #38 field/table collision: an exact `view.field` wins and the brief carries
  `ambiguous_anchor` (`test_navigate_two_part_anchor_prefers_exact_field_over_same_named_table`).
- #39 exists()/connect race: load_ir and cache_age_seconds open through one helper with
  `file:<abs>?mode=rw` (`test_load_ir_open_cannot_create_the_cache_even_if_exists_check_races`,
  `test_ir_cache_roundtrips_through_a_path_needing_uri_escaping`).
- #40 equal-instant ties: `_latest_iso` is a total order (parsed, instant, string)
  (`test_latest_iso_is_independent_of_row_order`).
- #33 own review: per-part backtick quoting and `${view}` refs
  (`test_sql_upstreams_backtick_per_part_quoting_and_view_refs`).
- #43 `clean --repo` deleting `<repo>/output`: Strata never writes there (dashboard defaults to
  `<cwd>/output/<repo>`, `strata outputs` requires `--out`), so the change is dropped and
  `test_clean_repo_never_deletes_output_inside_the_lookml_repo` fails if it returns.
- Local twin gate (Artemis P3s): per-part-quoted sql_table_name vs PDT upstream minted two
  nodes, and backtick-quoted CTEs became phantom tables — one `_unquote_table_ref` rule for
  both sides (`test_per_part_quoted_table_mints_one_node_for_view_and_pdt`,
  `test_sql_upstreams_backtick_quoted_cte_is_not_a_table`). Not fixed, pre-existing:
  load_configured_graph's cache_age_seconds→load_ir window (not a regression) and
  navigate chart filename collisions/length for sanitized anchors.
- Handoff-location P1 on every source PR: resolved by this single block.

### Gates

Re-run on the final code commit 669e188 (handoff-only commits after it): ruff check
  "All checks passed!", ruff format --check "211 files already formatted", mypy src "Success: no
  issues found in 87 source files", pytest "154 passed".

## 2026-11-03 — feat/registry-readiness (PR #44)

Moved here from `conductor/handoff/feat-registry-readiness.md` (folded into the archive by the
#45 update; this repo keeps handoffs in handoff-log.md only). Landed on main as c688a96.

Conductor Mode: patch. Context: research `2026-10-15-positioning-and-adoption.md` (registry + directory readiness). No tool behaviour changed; nothing published.

### What changed
- `README.md`: `mcp-name` token is now `<!-- mcp-name: io.github.G-Schumacher44/strata-oss -->` (was a visible, lower-cased `io.github.g-schumacher44/strata`; registry names are case-sensitive and must equal `server.json` `name`). The ~$45,000/month PDT figure is labelled as hand-authored `enterprise_mono` fixture data.
- `server.json` (new, unpublished): pypi package `strata-lookml` 0.1.8, stdio, `runtimeHint: uvx`.
- `pyproject.toml`: added console script `strata-lookml` (alias of `strata-mcp`) because the registry runs `uvx strata-lookml@<version>`, which needs an executable named after the distribution. Existing commands unchanged.
- `src/strata/mcp/server.py`: all 18 tools get `title` and `ToolAnnotations`. 17 read-only (`readOnlyHint=true`, `destructiveHint=false`, `openWorldHint=false`). `strata_render_chart` is `readOnlyHint=false, destructiveHint=true, idempotentHint=true`: it writes (and may overwrite) one HTML file under `~/.strata/output` or `/tmp`, and the README already calls it the one non-read-only tool. Deviation from "all readOnlyHint true": claiming read-only for a writer would be a false hint.
- Tests: `test_every_tool_has_title_and_explicit_read_only_stance` (allowlist over `list_tools()`, `WRITE_TOOLS` is the only exemption); `test_registry_manifest_matches_package_and_readme` (token matches `server.json` name, versions agree, identifier is a real script). `test_docs_consistency` regex widened for `@server.tool(...)`. Negative controls run: dropping a title, dropping the token each fail.

### Sources (primary)
- Registry PyPI verification, `mcp-name` token rules: modelcontextprotocol/registry `docs/modelcontextprotocol-io/package-types.mdx`
- server.json format and schema `2025-12-11`: `docs/reference/server-json/generic-server-json.md`, `static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`
- GitHub namespace `io.github.<user>/*`: modelcontextprotocol.io/registry/authentication
- Tool `title`, `ToolAnnotations`: MCP spec 2025-11-25 `server/tools` and `schema.ts`
- Claude directory: claude.com/docs/connectors/building/submission (title + readOnlyHint/destructiveHint on every tool; local servers only via a plugin; privacy section required for local connectors)

### Operator steps left (not done here)
1. After merge: bump version to 0.1.9 in `pyproject.toml`, `mcpb/manifest.json`, and `server.json` (both fields) and release to PyPI. The registry reads the README of the PUBLISHED version; 0.1.8 on PyPI carries the old token.
2. `mcp-publisher login github` then `mcp-publisher publish` from the repo root.
3. Claude directory: a plugin bundle (stdio is not accepted as a connector) plus a README "Privacy Policy" section. Not in this PR.
4. Other directories (Glama, Smithery, mcp.so, awesome-mcp-servers) per the research doc.

### Known, predates this PR
- Fresh clones need `git submodule update --init` or `test_pdt_ledger_unused_status_unaffected_by_zombie_detection` fails (fixtures are submodules).

## 2026-08-19 — fix/dashboard-innerhtml-escaping-sweep

Commit: 140f267 (Round 5 implementation commit — see below; this is a squash-merge
  repo, so post-merge the durable anchor becomes `gh pr view 30 --json mergeCommit
  -q .mergeCommit.oid`, but the handoff must anchor to a real commit while the PR is
  open, per Codex PR #30 r1 — a "set once merged" placeholder is not an anchor)
Conductor Mode: patch — single-file bug fix + guardrail hardening, no new slice (per
  `conductor/CONDUCTOR_MODES.md`'s Patch Mode: "bug fix, one-file change"). This repo has no
  `conductor/standard.json` (the koa-spawn HUB-skill governance script skips itself per its
  own instructions when that file is absent); scope came directly from GitHub issue #29 (a
  post-merge Artemis audit of PR #28 / slice-08, commit 6c9eede).
Context Budget: low — single-file bug-fix branch, no new slice.
Context Loaded: GitHub issue #29, src/strata/outputs/dashboard.py (full innerHTML/
  outerHTML/insertAdjacentHTML sweep), tests/test_l1_synthesis_outputs.py (the existing
  `test_data_derived_fields_are_escaped_in_innerhtml_templates` guardrail and its known
  blind spot), .github/workflows/strata-ci.yml (to match CI's gate scope exactly).
Context Skipped: handoff-archive.md beyond moving the completed slice-08 block into it;
  mcp/ and cli/ (out of scope — no CLI wiring touched).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump — pure dashboard-generator fix, no release trigger.

### Round 1 — issue #29, closed this branch

**What changed** (all in `src/strata/outputs/dashboard.py` unless noted):

1. **PDT Ledger "Used By" column** (was line 930) — `explores` local interpolated raw
   `${e}` (explore-key strings) into a nested template before splicing into
   `tr.innerHTML`. Now `${escapeHtml(e)}`.
2. **Migration Impact accordion** (was lines 1083-1085) — all three impact-group lists
   (`views`, `explores`, `fields`) interpolated raw `${v}` map-callback values into
   `content.innerHTML`. Now `${escapeHtml(v)}` in all three.
3. **Full-file sink sweep** (issue #29's item 3) found ONE MORE unescaped sink the
   original ask didn't name: the Cleanup Roadmap's action-label fallback —
   `const [cls, label] = actionStyle[r.action] || ['badge-gray', r.action];` — falls back
   to the raw `r.action` string for BOTH `cls` (CSS class slot) and `label` (visible
   text) when `r.action` isn't one of the three known keys. Both are now wrapped:
   `${escapeHtml(cls)}` and `${escapeHtml(label)}` (cls doesn't strictly need it today —
   every real `actionStyle` value is a literal — but it's derived from the same raw
   fallback as label, and this file's established invariant, per round 14's handoff
   entry, is "every record field routes through escapeHtml(), numerics included," not
   "escape only the ones provably exploitable today").
   Every other `innerHTML`/`outerHTML`/`insertAdjacentHTML` sink in the file was checked
   and is already safe: KPI cards (868), Dead Code Register (888), PDT Ledger's other
   cells (931), Schema Drift (1055), Migration Impact trigger label (1076), Node Detail
   panel (1212-1238) — all route data through `escapeHtml()` or one of the file's other
   safe-output helpers (`fmt_usd`, `fmt_bytes`, `primaryChipHtml`, `evidenceListHtml`,
   `consumerListHtml`, `detailRow`). `el()`'s optional third `html` arg (line 540) is
   never called with a third argument anywhere in the file today — not an active sink,
   left as-is (would need its own escaping discipline if a future caller starts passing
   one).
4. **Guardrail test hardened** — `test_data_derived_fields_are_escaped_in_innerhtml_
   templates` (tests/test_l1_synthesis_outputs.py) previously only matched literal
   `${r.field}` / `${c.field}` tokens, so it was structurally blind to interpolation
   through an intermediate variable (`${label}`) or a map-callback parameter (`${e}`,
   `${v}`) — exactly the class of the three fixes above. Replaced with a real (if
   heuristic) allowlist-based JS-template safety checker: extracts every `${...}`
   placeholder reaching an innerHTML-class sink (including ones nested inside a
   `.map()` callback's own template literal), and requires each to be provably safe —
   wrapped in `escapeHtml()`/a known-safe helper, a numeric/`.length`/`.toLocaleString()`
   expression, a ternary/`||`/`+`/`-` of safe parts, or a `.map(fn).join(literal)` chain
   whose callback body is itself safe. Bare local variables are resolved against a
   safe-var set inferred from their own `const`/`let` assignment — **scoped per
   top-level IIFE/function block**, not file-global, because this file has two unrelated
   locals both named `label` (one in `evidenceHtml()`, escapeHtml-derived; one in the
   roadmap IIFE, raw-fallback-derived) — a flat global safe-var set would have let the
   first one's safety leak into the second and silently defeated the whole check. This
   was caught DURING test-writing (not by CI), via manual mutation testing against the
   real file.
5. **CI JS syntax check added** — new `scripts/check_dashboard_js_syntax.py`: builds a
   dashboard from the `enterprise_mono` fixture (same fixtures the Python suite uses),
   extracts every `<script>` block, and runs each through `node --check` in a temp file.
   Wired into `.github/workflows/strata-ci.yml` as a step right after `Run tests`, with
   `actions/setup-node@v4` added alongside the existing `setup-python`. Skips (exit 0,
   stderr note) if `node` isn't on `PATH` rather than failing the job outright. This is
   the same class of check round-1's handoff (now archived) describes doing manually/
   ad-hoc each round (`new Function(src)` in Node) — now a standing CI gate instead of a
   per-round manual step.

**What was verified:**
- Full suite: **132 passed** (same count as before — the guardrail test was rewritten in
  place, not added alongside a new one).
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files, no issues — this command's
  scope doesn't cover `tests/`/`scripts/`, matching CI exactly).
- **Negative control (mandatory per issue #29 item 4):** four separate mutation runs,
  each reverting one of this branch's `escapeHtml()`/`.map()` fixes and re-running the
  guardrail test — all four went RED with a specific, correct offender reported, then
  were restored and the suite went green again:
  1. Reverted PDT Ledger `${escapeHtml(e)}` → `${e}`: test failed, reported
     `explores || '<span...>none</span>'` as the offending expression.
  2. Reverted Migration Impact `views` `${escapeHtml(v)}` → `${v}`: test failed,
     reported the bare `v` placeholder and the enclosing `.map(...).join('')` chain.
  3. Reverted roadmap `${escapeHtml(label)}` → `${label}`: test failed, reported `label`.
  4. Reverted roadmap `${escapeHtml(cls)}` → `${cls}`: test failed, reported `cls`.
- **CI JS-syntax-check negative control:** temporarily broke `escapeHtml`'s own syntax
  (`function escapeHtml(s) { if (`) — `scripts/check_dashboard_js_syntax.py` correctly
  exited 1 with a Node `SyntaxError` pointing at the injected block; restored, script
  passed again (5/5 blocks).
- `scripts/check_dashboard_js_syntax.py` run standalone against the real (fixed) branch:
  5/5 generated `<script>` blocks pass `node --check`.

**Exact Next Steps (Round 1, superseded by Round 2 below):**
1. ~~Open the PR (`Closes #29`)~~ — done, PR #30.
2. ~~Pre-gate ritual before pushing~~ — done.
3. No version bump / tag needed — generator + test + CI-only change, no release
   artifact touched. (Still true in Round 2.)
4. No follow-up slice implied by this branch. (Still true in Round 2.)

### Round 2 — PR #30 gate findings (Codex + Artemis), commit `61701a9`

**What changed** (all in `src/strata/outputs/dashboard.py` and
`tests/test_l1_synthesis_outputs.py` unless noted):

1. **Codex P1 — handoff anchor placeholder.** This block's `Commit:` field said
   "set once the PR is opened" instead of a real 7-char SHA even after the PR was open.
   Fixed: anchored to `61701a9` (the Round 2 implementation commit) above, with the
   post-squash resolution path kept as a note, not a substitute for a real anchor now.
2. **Codex P2 — `uniqueAnchor` on the safe-wrapper allowlist.** `uniqueAnchor(base)`
   returns `base` verbatim, unescaped — it's a DOM-id-collision disambiguator, not an
   escaping helper, so treating it as a safe wrapper in the guardrail's allowlist was
   wrong even though no template currently interpolates its result directly (both call
   sites — `roadmapId`, `driftAnchor` — only feed it to `primaryChipHtml()`, which
   escapes it, or a non-sink `.id =` assignment). Removed from `_SAFE_WRAPPERS`.
3. **Artemis should_fix — guardrail sink-shape coverage.** The guardrail only matched
   `.innerHTML =`/`.outerHTML =`/`.insertAdjacentHTML(...)` followed immediately by a
   template literal. Extended to also match `+=` on both properties, and to resolve a
   bare identifier assigned to a sink (`el.innerHTML = x;`) back to its own
   `const x = \`template\`;` declaration in the same top-level scope — flagging it as
   unresolved/unprovable if no such declaration exists, per the file's existing
   allowlist-of-safe-shapes philosophy.
4. **`el()`'s dead third `html` parameter removed.** It was the one bare-identifier-
   into-innerHTML shape already in the file with no resolvable declaration (a plain
   function parameter) — grep confirmed no caller ever passes a third argument, so
   rather than special-case unreachable dead code in the guardrail, deleted the
   parameter and its `e.innerHTML = html` branch.

**What was verified:**
- Full suite: **132 passed**.
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files).
- `scripts/check_dashboard_js_syntax.py`: 5/5 generated `<script>` blocks pass
  `node --check`.
- **Negative control (mandatory, one per newly-covered shape) — each mutation applied
  to the real roadmap-row template in `dashboard.py`, guardrail run, reverted:**
  1. Added `${uniqueAnchor(r.action)}` as a direct interpolation → guardrail correctly
     went RED, reporting `uniqueAnchor(r.action)` as the offending expression.
  2. Added `li.innerHTML += \`${r.action}\`;` → RED, reported `r.action`.
  3. Added `const mutationHtml = \`${r.action}\`; li.innerHTML = mutationHtml;` → RED,
     resolved through the new template-var lookup and reported `r.action`.
  4. Added `li.innerHTML = someUnresolvedMutationVar;` (no matching declaration) → RED,
     reported `unresolved variable \`someUnresolvedMutationVar\` assigned to sink`.
  All four restored; suite green again after each.

**Known, intentionally out-of-scope gap:** `panel.innerHTML = rows.join('');` (node
detail panel) is a sink assignment the guardrail still does not trace — `rows` is built
via repeated `.push(...)` calls (each pushing the result of a safe wrapper:
`detailRow`/`statusBadge`/`consumerListHtml`), not a single provably-safe RHS expression
the existing `_is_safe_expr` machinery can evaluate. Manually verified safe (every
pushed value already routes through a safe wrapper). Tracing multi-statement array-push
accumulation was not part of the three sink shapes named in the Artemis finding and
would be a meaningfully larger change (push-site tracking, not sink-site tracking) —
left as a follow-up if a future review wants it, not silently declared "covered."

### Round 3 — PR #30 round-2 gate findings (Codex), commit set below

**What changed:**

1. **Codex P1 — invalid `Conductor Mode: none`.** `none` isn't a value in
   `conductor/CONDUCTOR_MODES.md`'s vocabulary (`patch | slice | full | audit`). Reclassified
   this whole branch as `patch` mode (matches its own "bug fix, one-file change" definition)
   in the block header above; kept the honest "no `standard.json`" detail as context, not a
   substitute for a real mode.
2. **Codex P2 — `detailRow` wrongly in `_SAFE_WRAPPERS`.** Audited every one of the (then
   nine) allowlisted helpers against its real `dashboard.py` implementation, one by one:
   `escapeHtml`, `fmt_usd`, `fmt_bytes`, `primaryChipHtml`, `evidenceListHtml`,
   `consumerListHtml`, `statusBadge`, `evidenceHtml` all escape/derive every data-derived
   value they interpolate from their OWN body — unconditionally safe regardless of what's
   passed in, so they stay in `_SAFE_WRAPPERS` (each one's reasoning is now a comment above
   the tuple in `tests/test_l1_synthesis_outputs.py`). `detailRow(key, valHtml)` is the one
   exception: it escapes `key` but returns `valHtml` **verbatim** — every real call site
   already escapes its second argument (confirmed by reading all 8 call sites), but the
   helper itself doesn't, so `${detailRow('X', r.name)}` would have passed the guardrail
   with a raw, unescaped second argument. Moved `detailRow` out of `_SAFE_WRAPPERS` into a
   new `_ARG_SAFE_WRAPPERS` tier: a call to one of these names is safe only when EVERY
   argument passed to it is itself provably safe (recursed via the checker's existing
   `_is_safe_expr` rules, using a new `_call_args()` helper to extract them) — not merely
   because the callee's name is on a list. (Considered making this generic to any function
   call, not just an explicit tier — rejected: e.g. `const d = evt.target.data();` is a
   zero-argument call whose result is raw untrusted data, not literal HTML built from its
   arguments; a name-scoped tier avoids misclassifying that shape as safe.)

**What was verified:**
- Full suite: **132 passed**.
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files).
- `scripts/check_dashboard_js_syntax.py`: 5/5 generated `<script>` blocks pass `node --check`.
- **Negative control (mandatory):** temporarily added `${detailRow('X', r.name)}` to the Dead
  Code Table's existing `tr.innerHTML` template (`r` already in scope there from the row's
  `.forEach(r => ...)` callback) — guardrail correctly went RED, reporting
  `detailRow('X', r.name)` as the offender. Reverted.
- **Positive control:** same spot with `${detailRow('X', escapeHtml(r.name))}` — guardrail
  correctly stayed GREEN (proves the new arg-recursion isn't overly strict). Reverted; `git
  diff src/strata/outputs/dashboard.py` confirmed empty before committing.

**Exact Next Steps (Round 3, superseded by Round 4 below):**
1. Push this branch; reply to both round-2 Codex inline threads (mode vocabulary,
   `detailRow` allowlist) describing the fix — replying is not resolving, resolution follows
   re-gate.
2. Re-run the gate on PR #30.
3. No version bump / tag needed.
4. No follow-up slice implied; the `rows.join('')` gap (Round 2, above) is still a candidate
   for a small follow-up if anyone wants the guardrail to trace array-accumulation sinks too,
   not a blocker for this PR.

### Round 4 — PR #30 round-3 gate finding (Codex), commit set below

**What changed** (`tests/test_l1_synthesis_outputs.py` only — no `dashboard.py` change was
needed; see verification below):

1. **Codex P1 — `.toLocaleString()` safe-ending trusted the wrong thing.** The guardrail's
   `_is_safe_expr` treated ANY expression ending in `.toLocaleString()` as safe, reasoning
   it only ever formats numbers. Wrong: `String.prototype.toLocaleString` exists too and
   returns the string UNCHANGED, so `${r.name.toLocaleString()}` (raw untrusted string,
   receiver never proven numeric) would have passed the checker unescaped — the same class
   of bug as Round 3's `detailRow` finding (trusting a method NAME instead of what it does
   with its receiver). Fixed: `.toLocaleString()` is now safe only when its receiver passes
   a new, narrower `_is_safe_numeric_expr` — numeric literal, `Number(...)`, `.length`,
   parenthesized/arithmetic (`+ - * /`) combinations of the same, or nothing else. This is
   deliberately NOT the same as `_is_safe_expr` ("won't inject HTML"): an already-escaped
   string is injection-safe but not numeric, and `'<img>'.toLocaleString() === '<img>'`
   proves generic safety isn't sufficient for this specific method ending.
2. **Audited every other method-based safe ending in the checker for the same mistrust
   shape** (per the finding's instruction to check `.toFixed()` and similar): the only
   other such ending is `.length` (line ~973), which is safe unconditionally — `.length` on
   a string/array is always a JS number by spec, no receiver-type ambiguity exists the way
   it does for `toLocaleString`/`toFixed`/`toPrecision`. `.toFixed()` does NOT appear
   anywhere in the checker's safe-endings list — the file's only two `.toFixed()` calls
   live inside `fmt_bytes`/`fmt_usd`'s own bodies (already unconditionally-safe entries in
   `_SAFE_WRAPPERS`, trusted as whole-function calls, not via a safe-ending regex), so
   there was nothing to change there.
3. **No real `dashboard.py` call site needed a change.** Audited all three real
   `.toLocaleString()` call sites (`total_queries||0`, `query_count||0`, `build_count||0`,
   all `<numeric-field>||0` shapes): none of them is ever the direct subject of a `${...}`
   interpolation inside an innerHTML-class sink template — the KPI-card one flows through
   `${escapeHtml(c.value)}` one level removed (already safe regardless of `c.value`'s
   content), and the two `detailRow(...)` ones build the node-detail-panel's `rows` array
   via `.push()`, which is the `rows.join('')` array-accumulation gap Round 2's handoff
   already documented as out of the guardrail's traced-sink scope. So tightening the
   safe-ending rule changed zero real templates — confirmed by the unmodified full suite
   passing and `git diff src/strata/outputs/dashboard.py` staying empty throughout.

**What was verified:**
- Full suite: **132 passed**.
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files).
- `scripts/check_dashboard_js_syntax.py`: 5/5 generated `<script>` blocks pass `node --check`.
- **Negative control (mandatory, exact shape from the finding):** temporarily changed the
  Dead Code Register's `source_file` cell from `${escapeHtml(r.source_file||'')}` to
  `${r.name.toLocaleString()}` (`r` already in scope from that row's `.forEach(r => ...)`)
  — guardrail correctly went RED, reporting `line 4843: r.name.toLocaleString()` as the
  offender. Reverted.
- **Positive control:** same spot with a numeric-literal receiver,
  `${(1234).toLocaleString()}` — guardrail correctly stayed GREEN (proves the new
  receiver-provability check isn't overly strict for the legitimate case). Reverted; `git
  diff src/strata/outputs/dashboard.py` confirmed empty before committing.

**Exact Next Steps (Round 4, superseded by Round 5 below):**
1. Push this branch; reply to the round-3 Codex inline thread (`.toLocaleString()`
   receiver-provability) describing the fix — replying is not resolving, resolution follows
   re-gate.
2. Re-run the gate on PR #30.
3. No version bump / tag needed.
4. No follow-up slice implied; the `rows.join('')` gap (Round 2) remains the one
   documented, intentionally out-of-scope tracing gap.

### Round 5 — PR #30 round-4 gate findings (Codex), commit 140f267 — FINAL checker-heuristic round

**What changed** (both `src/strata/outputs/dashboard.py` and
`tests/test_l1_synthesis_outputs.py`; commit 140f267):

1. **Codex — `fmt_bytes` was wrongly unconditionally-safe.** It sat in
   `_SAFE_WRAPPERS` alongside `fmt_usd`, but the two are NOT siblings the way the
   comment claimed. `fmt_usd`'s only body is `'$' + v.toFixed(2)` — `.toFixed`
   exists exclusively on `Number.prototype`, so any non-number argument makes
   `v.toFixed` `undefined` and calling it throws a `TypeError` before the `+`
   ever runs; there is no path back to input-derived text, so it legitimately
   stays unconditional (documented in a new, longer `_SAFE_WRAPPERS` comment).
   `fmt_bytes` is different: its four `b >= 1eN` threshold checks all evaluate
   to `false` for a non-numeric string (`>=` coerces via `ToNumber`, and every
   `NaN` comparison is `false`), so a string argument falls through every
   threshold to the final `return b + ' B'` — and for a string `b` that `+` is
   concatenation, not arithmetic, returning the input **verbatim** with `' B'`
   appended. `${fmt_bytes(r.name)}` would have passed the old allowlist
   unescaped. Moved `fmt_bytes` into `_ARG_SAFE_WRAPPERS` (same tier as
   `detailRow` — every argument must itself be independently proven safe).
2. **Codex — `.length` was trusted as an unconditionally-safe ending.** Every
   value this checker inspects is JSON-parsed record data, and a plain object
   can carry an own property literally named `length`
   (`r.length === '<img ...>'`) that shadows the real Array/String `.length`
   accessor entirely — `r.length` then returns that string, not a count. A
   genuine Array's or primitive String's `.length` IS always numeric (the JS
   engine won't let you assign it anything else), but the checker has no way to
   prove syntactically that a given receiver is actually one of those rather
   than a generic record. Dropped the unconditional `.length` trust from BOTH
   `_is_safe_expr` (the general HTML-safety prover) and `_is_safe_numeric_expr`
   (the narrower numeric prover round 3 introduced for `.toLocaleString()`
   receivers — it had the exact same blind spot, e.g.
   `r.length.toLocaleString()`).
3. **`Number` added to `_SAFE_WRAPPERS`** as the honest replacement for both of
   the above: `Number(x)` can only ever evaluate to a primitive number or
   `NaN` — there is no code path back to a string, so a template-literal
   coercion of its result is always digits/`NaN`/`Infinity`, never attacker
   text, regardless of what `x` is. This is the same "wrap it, don't
   special-case the checker" move the finding's brief required.
4. **Restructured every real `dashboard.py` call site** that needed it, in both
   directions — sink-scanned AND the `rows.join('')` sink the checker still
   can't trace (round 2's documented gap; fixing the *runtime* bug there too,
   since it's a real innerHTML sink even though the heuristic can't see it, not
   just a checker-satisfaction exercise):
   - `pdtCostSentence`'s `fmt_bytes(bytesProcessed || 0)` →
     `fmt_bytes(Number(bytesProcessed || 0))` (textContent-only sink, fixed for
     the underlying `fmt_bytes` correctness, not because the checker sees it).
   - PDT Ledger row: `fmt_bytes(r.bytes_processed)` →
     `fmt_bytes(Number(r.bytes_processed))` (real sink-scanned site).
   - Node-detail panel (`rows.join('')` sink): `fmt_bytes(d.bytes_processed||0)`
     → `fmt_bytes(Number(d.bytes_processed||0))`.
   - Cleanup Roadmap's `evCount` local: `(r.evidence_ids||[]).length` →
     `Number((r.evidence_ids||[]).length)` (this one WAS sink-scanned — `evCount`
     feeds `${evCount}` inside `li.innerHTML`, and `_safe_vars_for_scope` stopped
     trusting its assignment the moment the blanket `.length` rule was dropped;
     confirmed by rerunning the full suite, which would have gone RED here if
     left unwrapped).
   - Migration Impact accordion: both `(r.explores||[]).length` and
     `(r.fields||[]).length` occurrences used as direct interpolation values
     (not the ternary conditions — a ternary's condition branch is never
     rendered, so it doesn't need proving, and both leftover raw `.length`
     conditions were left untouched on purpose).
   - Node-detail panel's `views.length` → `Number(views.length)` (also a
     `rows.join('')`-sink site, same runtime-correctness reasoning as
     `d.bytes_processed` above).

**What was verified:**
- Full suite: **132 passed**.
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files).
- `scripts/check_dashboard_js_syntax.py`: 5/5 generated `<script>` blocks pass `node --check`.
- **Negative controls (mandatory, exact shapes from the finding), checked by calling the
  checker's prover functions directly (`_is_safe_expr`/`_is_safe_numeric_expr` imported from
  the test module) rather than mutating and reverting dashboard.py, since neither shape has a
  real call site to temporarily mutate:**
  - `fmt_bytes(r.name)` → `_is_safe_expr(...)` returns `False` (RED), correctly caught by the
    new `_ARG_SAFE_WRAPPERS` entry.
  - `r.length` → both `_is_safe_expr(...)` and `_is_safe_numeric_expr(...)` return `False`
    (RED) now that the blanket `.length` trust is gone from both provers.
- **Positive controls**, same direct-call method, confirming the real fixed patterns stay
  GREEN: `fmt_bytes(Number(r.bytes_processed))`, `fmt_usd(r.estimated_cost_usd)` (unchanged,
  still unconditional), `Number((r.explores||[]).length)`,
  `Number((r.fields||[]).length)-8` (the arithmetic residual after wrapping the base),
  `Number(views.length)` — all `True`.
- The full-fixture sweep test (`test_data_derived_fields_are_escaped_in_innerhtml_templates`,
  which runs the checker end-to-end against the real generated enterprise_mono HTML, not just
  synthetic expressions) passed both before AND after every dashboard.py wrap, confirming the
  `evCount`/`explores`/`fields` real sites needed the fix (they'd have gone RED without the
  `Number(...)` wrap once the blanket `.length` rule was removed) and that nothing else broke.

**Exact Next Steps:**
1. Push this branch; reply to all three round-4 Codex inline threads (`fmt_bytes`
   allowlist, `.length` safe-ending, handoff anchor) describing the fixes — replying is not
   resolving, resolution follows re-gate.
2. Re-run the gate on PR #30. Per the task brief, this is the FINAL round for
   checker-heuristic findings — if Codex round 5 raises a NEW heuristic gap, treat it as
   requiring a written justification for why the class of bug (`_SAFE_WRAPPERS` trusting a
   name instead of a body, or a safe-ending regex trusting a syntax shape instead of a
   receiver type) wasn't fully closed by rounds 2-5, rather than another one-off patch.
3. No version bump / tag needed.
4. No follow-up slice implied; the `rows.join('')` array-accumulation sink-tracing gap
   (documented since Round 2) remains the one intentionally out-of-scope item — this round
   fixed the two REAL vulnerabilities that happened to live behind it (`d.bytes_processed`,
   `views.length`) without closing the general tracing gap itself.

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
