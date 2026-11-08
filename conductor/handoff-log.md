# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

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
