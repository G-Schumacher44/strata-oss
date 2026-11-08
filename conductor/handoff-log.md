# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/s1-error-contract (one error contract for MCP and CLI, spec S1)

Commit: d324871
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S1 (D2; findings B5, B7, U3, U6, U12) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§1, findings, D2, S1), mcp/tools.py, mcp/server.py, navigate.py, validation.py, pipeline.py, viz/render.py, cli/{main,query,auth,skill,build_ir}.py, the installed mcp 2.3.0 `mcpserver/exceptions.py` + `tools/base.py`.
Exact Next Steps: twin gate on the PR, operator merges. If S0 (generated reference) lands first, merge `origin/main` and re-run `python scripts/gen_reference.py`. Then wave B (S2 ∥ S4 ∥ S6 ∥ S10) builds on this contract: S2's unknown-skill-lists-names is already done here (the hint lists them); S4's `check` integrity failures should raise `StrataError` rather than add a second exit path.

### What changed

- `src/strata_lookml/errors.py`: `StrataError(ToolError)` (`mcp.server.mcpserver.exceptions.ToolError`, verified in the installed 2.3.0) with `NotFound` (`not_found`) and `InvalidInput` (`invalid_input`); fields `code`/`message`/`hint`; `str()` = `<message> Hint: <hint>`; `to_dict()` = the CLI JSON envelope.
- Raised from: `mcp/tools.py` (unknown field/explore/table/skill/model, bad orphan/find-field kind, render_chart path guard + YAML/JSON parse), `navigate.py` (no match), `validation.py` (bad `kind:name` / object), `pipeline._repo_graph` (missing repo, no `.lkml`; every pipeline entry point builds through it), `viz/render.py` (symlink guard, spec must be a mapping). `ir/parser.lkml_paths` is now the one .lkml discovery used by both `parse_repo` and the repo check. The duplicate repo check in `cli/build_ir.py` is gone.
- CLI seam `cli/_contract.py`: `StrataGroup` is the root group class (stderr `Error:`/`Hint:`, exit 1); `JsonCommand` on all `query` subcommands, `build`, `auth status` (stdout envelope; only with `--json` on commands that have that flag). No per-command try/except. `strata-chart` (argparse) has its one seam in `render.main`. `strata skill <unknown>` keeps exit 1, now through the seam.
- `auth status` without a token: `NotFound` with hint naming `strata auth login`; unsafe permissions → `InvalidInput` (message has the chmod).
- `pyproject` floor `mcp>=2.3,<3`. README "Error handling" (under CLI). Navigator skill text updated to the new failure shape. `scripts/test_mcp_live.py` catches `StrataError`.

### Deviation from the spec

- D2 has `errors.py` import the SDK's `ToolError`, but importing any `mcp.*` module runs `mcp/__init__`, which pulls httpx; `test_l0_no_network_imports` (pipeline is L0) failed with an eager import. `pipeline.py` therefore imports the error classes at raise time. Every other module imports them at the top. The L0 test is the negative control (eager import → it fails).

### Gates

pytest 229 passed (217 before; +12 in `tests/test_error_contract.py`), ruff check + format --check clean, mypy clean, dashboard JS check pass, the three CI `strata check` scenarios pass, `strata validate` 10 passed. All 12 new tests fail against the pre-change tree (origin/main 5ac4572). Seam mutations, each failing only its own test: StrataError base → Exception (5 MCP cases), StrataGroup catch removed (CLI envelope/hint), `as_json` gate removed (navigate human stdout), lkml check removed (empty repo), repo-dir check removed (`/nonexistent` → not_found), strata-chart catch removed, auth pre-check removed, view_sources model check removed, eager errors import in pipeline (L0 test).
