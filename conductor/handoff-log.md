# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/wb-s5-findings (Findings triage page + keyboard map; workbench S5)

Commit: 81b946f
  (Latest implementation commit: merge of origin/main a0b5e1a (S6 #90) + the G19 single PR-comment builder; earlier 48bdcb0 (review round 2), earlier 363b5be (review round 1 + post-merge fix), 11f4739 (merge of origin/main 1cf80cb, S7 #89), 0c52ad7. The PR squash-merges.)
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

