# fix/dashboard-host-check

**Commit anchor:** branched from `origin/main` @ `4b21b84`.

## Change
- `src/strata_lookml/cli/dashboard.py`: new `allowed_hosts(port)` / `make_handler(port)`. The static
  handler now answers 403 (no body content) unless the `Host` header is exactly
  `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>` (case-insensitive). Missing, foreign,
  wrong-port and port-less hosts are refused. Allowlist only; enforced in `send_head` (GET + HEAD).
- `tests/test_dashboard_host.py`: loopback forms served; foreign / wrong-port / port-less / empty /
  missing Host refused with 403 and no artifact content.
- `CHANGELOG.md` (Unreleased > Security), `docs/security-hardening.md` (Network Surface).

## Verification
- `pytest`: 191 passed, 1 failed (`test_pdt_ledger_unused_status_unaffected_by_zombie_detection`,
  fails identically on clean `origin/main`; unrelated). New file: 11 passed.
- ruff check, ruff format --check, mypy src: clean.
- Negative control: with the allowlist check disabled, 7 of 11 new tests fail; restored, 11 pass.
