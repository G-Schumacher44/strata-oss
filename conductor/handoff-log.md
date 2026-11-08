# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

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
