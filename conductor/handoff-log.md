# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

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
