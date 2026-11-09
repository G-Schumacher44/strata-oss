# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/wb-s6-detail (detail pages; workbench S6)

Commit: 0d92a18
  (Latest implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S6 of `workbench-spec-2026-11-08.md` (D2 page-to-reads table, §4 Detail wireframe, §6b M5/M7).
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D2, §4, §5 S6, §6b), the approved mockup (detail frame CSS, `detailFrame`, `prText`), workbench/{app,index,render}.py + templates, links.py, gate.py, mcp/tools.py `strata_object`, synthesis/{slices,verdicts}.py, outputs/artifacts.py, tests/test_workbench_server.py.
Exact Next Steps: twin gate, operator merges. S5 (findings) and S7 (overview) share `_layout.html` / `_base.html`: the detail frame carries its own scoped CSS (`.detail`) and only the `head` block is extended, so a layout restyle should not collide. S9 turns the disabled Acknowledge buttons on (`_lineage.html` `finding_cards`).

### What changed

- `workbench/detail.py`: `Detail(workbench, roadmap)` builds plain-data view models (no markup): `object_page(obj)` and `finding_page(id, records)`. Verdict: explore = `deterministic_verdict(build_explore_slice(...))`; everything else = the first matching `cleanup_roadmap` item (a table also matches roadmap items whose evidence names its `schema_table:`), else "NO ACTION". Lineage groups come from `strata_object` upstream/downstream, each member a link only when its node exists and has a page (explore keys resolve through `explores_by_key`; an ambiguous key links to its candidates page). Marks: `dead` / `zombie` from the findings on the node (a view also reads its `pdt:` node; zombie wins). Content: `content is None` or `content_checked` false -> "not loaded" note, never a 0.
- `workbench/pr_text.py`: `pr_comment(records, obj, workbench_base=None, verdict=None) -> str`, pure, shaped like the mockup's `prText`; no base -> no `Workbench:` line (M7); no records -> a comment about the object with its verdict. Also owns `CATEGORY_LABELS`, `ACTION_LABELS`, `CATEGORY_ACTIONS`, `usd`.
- `outputs/artifacts.py`: `_cleanup_roadmap` -> public `cleanup_roadmap`, unchanged behaviour.
- Templates: `_detail_frame.html` (scoped CSS from the mockup tokens, light/dark by `prefers-color-scheme`, crumbs, header, verdict, side cards, readonly PR-comment textarea), `_lineage.html` macros, `detail.html`, `finding.html`. No inline script or style attributes.
- `assets/js/detail.js` (allow-listed as `/static/detail.js`): copy buttons via `data-copy` / `data-copy-from`, textContent only.
- `app.py`: `_object` / `_finding` render the new pages; ambiguous/unknown behaviour unchanged (300/404/400).

### Deviations from the brief

- No "Open in graph" link (the graph page is still a placeholder; S8).
- Status pills are `new` / `baselined` only: `acknowledged` comes from the triage store, which the HTTP adapter (S9) wires in.
- Rebuild cost in the PR comment has no "over N days" suffix (the finding record carries no window).
- The hostile-fixture test now allows exactly one external script tag (`/static/detail.js`) and the frame's tags/attributes; any other script still fails it.

### Gates

pytest 619 passed, 1 skipped (22 new in `tests/test_workbench_detail.py`); ruff check + format --check clean; mypy clean; `check_dashboard_js_syntax.py` passes; `node --check` on detail.js; `gen_reference.py --check` clean. Fail-before: the new test file against a detached worktree of origin/main (b7f7f7f, PYTHONPATH pinned to it; the import of `cleanup_roadmap` and `pr_comment` stubbed so it collects) -> 21 failed, 1 passed (the roadmap one).
