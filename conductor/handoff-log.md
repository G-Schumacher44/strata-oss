# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

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
