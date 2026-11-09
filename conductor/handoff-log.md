# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/wb-s9-triage-post (acknowledge from the web; workbench S9)

Commit: 0d6ef05
  (Latest implementation commit: the /api/pr-comment review test; earlier 8de7e13 (the triage POST). The PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S9 of `workbench-spec-2026-11-08.md` (D4, D6, §5 S9). Codex-gated: the workbench's only write.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D4, D6, §5, §6b), workbench/{app,server,detail}.py + templates, triage.py, cli/findings.py (`strata ack`), cli/dashboard.py (`allowed_hosts`, `bind_server`), assets/js/{workbench,detail}.js, docs/security-hardening.md, tests/test_workbench_{server,findings,detail}.py.
Exact Next Steps: Codex + twin gate, operator merges. S10 (static export) must render no triage controls: the export has no server, so the `data-triage` buttons and the Findings action bar's ack buttons must be absent there, not just disabled. S8 (parallel lane) also edits `workbench.js` and `app.py`; S9's code is one block in each (`// --- triage writes` and `# --- the one write`).

### What changed

- `workbench/app.py`: `respond` takes optional `headers` and `read` (the body reader). After the Host check, `/api/triage` goes to `_triage_post` for every method: anything but POST (OPTIONS, GET, HEAD included) is a JSON 405 with `Allow: POST` and no CORS headers. `_write_request` runs the checks, all before the body is read: `Origin == "http://" + Host` (missing, `null`, another host or port, `https`, or a different allow-listed name are 403), `Sec-Fetch-Site` is `same-origin` when sent (403), `Content-Type` exactly `application/json` (415), `X-Strata-Token` via `hmac.compare_digest` (403), `Content-Length` present (411; any `Transfer-Encoding` is 411 too), numeric (400), at most `MAX_TRIAGE_BODY` = 64 KB (413). A duplicated checked header is 400; a body shorter than its length (or a read that times out) is 400. `_triage_payload` then allows exactly `{action: "ack"|"unack", ids: non-empty list of non-empty strings, note?: string with ack only}` (400). Only then is `TriageStore.acknowledge`/`unacknowledge` called: its `InvalidInput` (id outside the allowlist, note over 2000 chars) is 400, any other `StrataError` (concurrency retries exhausted) 409, both as `{error, code, hint}`. Success returns `{rows: [{id, status, label, acked_at, note}], untracked: [...]}` read through `_triage_rows` (the one status source); `label` is `pages.findings.STATUS_LABELS`. Every response on the path is `_embed_json` (no raw `<`), never HTML.
- `workbench/server.py`: `do_POST` dispatches like the others, passing `self.headers.items()` (duplicates preserved) and `_read_body`, which sets a `BODY_TIMEOUT_S` = 5 s socket timeout before `rfile.read(length)` (the server is single-threaded). Non-GET/HEAD connections still close after the response.
- `workbench.js`: one `// --- triage writes` block: `postTriage` (fetch with `Content-Type: application/json` and the `<meta name="strata-token">` value), `triageFailed` (toast with error + hint), `setStatusText` (textContent; keeps the pill dot). Findings `a`/`u` and the action-bar buttons call `triage(action)` over the selected rows, else the cursor row, and repaint each row's status cell from the response row of its lead id. A note input in the action bar goes with `a` (Enter in it acknowledges). Detail and finding page cards: every `[data-triage]` button is enabled by the script, toggles ack/unack, and repaints the card's pill and its "acknowledged <at> · note" line.
- Templates: `findings.html` (note input, live buttons, `data-status` on the status cell), `_lineage.html` (card button `data-triage`/`data-triage-id`, disabled in the HTML with a `strata ack` hint so no-JS pages stay read-only; `data-status` pill; `data-acked` line always present, `hidden` when not acked), `_layout.html` help text. `workbench.css`: the note input.
- Docs: `docs/security-hardening.md` (the write endpoint and each check, the write table row, the 405 rule), README workbench paragraph, CHANGELOG Added.

### Deviations from the brief

- The adapter lives in `app.py` (`App._triage_post` + module helpers), not `server.py`: `app.py` is where the route table, the Host check and the store already are, and it is testable without a socket. `server.py` only reads the body, bounded and with a timeout.
- Origin must equal `http://` + the request's own Host, which is stricter than "any allowed host": a page on `127.0.0.1:p` posting with `Host: localhost:p` is refused. The page's `fetch` uses a relative URL, so a real page never hits this.
- Status codes per failure are the precise ones (403 Origin/fetch-site/token, 415 type, 411/400/413 length, 400 shape), not only 403/400. All are 4xx with the store untouched.
- The detail-page ack controls are driven from `workbench.js` (loaded on every page before `detail.js`), not `detail.js`, so there is one POST client. `detail.js` is unchanged.
- The optional note input is on the Findings action bar only. The detail card buttons send no note (re-acknowledging keeps a stored note, per `TriageStore`).

### Gates

pytest 723 passed, 1 skipped (base origin/main ff1b714: 672 passed, 1 skipped; +51: `tests/test_workbench_triage_post.py` is new, `test_workbench_detail.py` updated for the live controls); ruff check + ruff format --check clean on src/ tests/ scripts/; mypy clean (115 files); `check_dashboard_js_syntax.py`: 5 generated blocks + 2 static scripts pass `node --check`; the existing sink scan over `workbench.js` is clean; `gen_reference.py` produced no change.
Fail-before: the new test file run against a throwaway detached worktree of origin/main: 50 failed, 1 passed (the case-coverage check). The worktree was removed.
Negative controls (each check mutated out of `app.py`, restored from a copy, `cmp` clean): Origin check removed → 8 fail; missing Origin allowed → 2; Sec-Fetch-Site → 3; Content-Type → 5; token → 3; 64 KB cap → 1; Content-Length required → 1; duplicate-header rule → 1; extra-key rule → 1. Every refusal case asserts no `TriageStore` method ran (class spy over acknowledge/unacknowledge/observe/snapshot/_mutate) and the store file is byte-identical.
Concurrency: `strata ack` in a subprocess while the live server took 29 POSTs; every id from both sides is acked afterwards. Stalled body: a request 3 bytes short gets 400 after the timeout and the next POST succeeds.
Visual (headless Chrome, isolated profile `dev_project_tmp/wb-s9/chrome-profile`, server on 18931 with HOME in `dev_project_tmp/wb-s9/home`, both stopped afterwards): `a` on the cursor row flipped the pill new → ack (`findings-after-a.png`), the Acknowledged tab lists it after a reload (`findings-acknowledged-tab.png`), `u` flipped it back, a note typed with Enter was stored, a stale token showed the toast "missing or wrong page token — Reload the page ..." (`findings-error-toast.png`), the detail card button toggled ack/unack with pill and acknowledged line repainted (`detail-after-ack.png`), and with JS disabled the card button is disabled (`detail-nojs.png`). No console errors.

### Addendum: review of `GET /api/pr-comment` (S5's read-only route)

- No gap found, so no behaviour change. Host is checked before routing (403, plain text, no page). Every method other than GET and HEAD gets 405 with `Allow: GET, HEAD`. Successes are `text/plain` with `nosniff`. The server never sends an `Access-Control-*` header on any response, so a cross-origin page can send the GET but cannot read the answer.
- Ids are dictionary lookups into `findings_by_id`. Unknown ids are skipped; if none match, the 404 says "no current finding among the requested ids" without the ids. The comment text is built from finding records, never from the request.
- New test in 0d6ef05: `test_pr_comment_route_is_read_only_host_checked_and_never_cors_readable`. It sends GET/HEAD/POST/OPTIONS/PUT with a cross-origin `Origin` and checks that no CORS header comes back, POST/OPTIONS/PUT get 405, the content type and nosniff are right, a hostile unknown id gets 404 that does not echo it, and a foreign Host gets the bare 403. Negative controls: adding `Access-Control-Allow-Origin: *` to `_response` fails it, and echoing the ids in the 404 message fails it.
- Gates: pytest 724 passed, 1 skipped. ruff, ruff format, mypy and JS syntax are clean.
