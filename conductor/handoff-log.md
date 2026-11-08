# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

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
