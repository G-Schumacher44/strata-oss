# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/s12-port-fallback (dashboard port fallback, spec S12)

Commit: 20844cc
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

### Gates

pytest 336 passed (7 in `tests/test_dashboard_port.py`, on self-bound high ports; `DEFAULT_PORT`/`FALLBACK_PORTS` monkeypatched, never the real 8765), ruff check and format --check clean, mypy `src/strata_lookml` clean. Negative control: on a detached origin/main worktree the new tests error (no `DEFAULT_PORT`); mutating `make_handler(candidate)` to the requested port fails the allow-list test, and treating `--port` as never explicit fails both explicit-port tests.
