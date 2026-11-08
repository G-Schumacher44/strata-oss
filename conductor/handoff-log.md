# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/s2-mcp-envelope (MCP list envelope + agent descriptions, spec S2)

Commit: 315b540
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S2 (D3, D5; findings U1, U2, U10 partial, N6) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§1, U1/U2/U10/N6, D3, D5, S2), mcp/server.py, mcp/tools.py, l1/enrich.py `analysis_coverage`, tests/test_error_contract.py.
Exact Next Steps: twin gate on the PR, operator merges. If another wave-B lane lands first, merge `origin/main`, hand-resolve this log + CHANGELOG, re-run `python scripts/gen_reference.py`. S3 (identifier resolution) builds on this; S7 (cache identity) should keep `usage_checked`/`schema_checked` sourced from `analysis_coverage`.

### What changed

- `mcp/tools.py`: `list_envelope` / `l1_list_envelope` (the one `{"items","count"}` shape; L1 variant adds `usage_checked` or `schema_checked` plus a `hint` naming `STRATA_USAGE_FIXTURE` / `STRATA_SCHEMA_FIXTURE` when that check did not run). `strata_usage_summary` gains `usage_checked`, `schema_checked`, `hint` from `analysis_coverage()`; `has_l1` kept, documented deprecated (N6). `strata_find_field` takes `limit` (default 50, max 200, `InvalidInput` outside).
- `mcp/server.py`: the six list tools return the envelope; `MCPServer(..., instructions=...)`; every parameter is `Annotated[..., Field(description, examples)]`; tool descriptions state input format, failure modes, prerequisites; `find_field` `query` `min_length=2`; `render_chart` states the sandbox and column contract and keeps its destructive annotation. The semantic_layer_audit skill now checks `usage_checked`.
- The envelope is applied at the MCP seam only; the tool functions still return bare lists, so CLI output (`strata query orphans`, `strata skill`) is unchanged.
- `docs/reference.md` regenerated; CHANGELOG Unreleased/Changed "Breaking, MCP output shape".

### Deviations from the spec

- D3 says L1 tools add `has_l1` + hint; per the lane brief they add the specific `usage_checked` / `schema_checked` flag instead (`has_l1` only survives on `strata_usage_summary`, deprecated).
- `strata_render_chart` column contract is documented in its description, not enforced (enforcement is S10).

### Gates

pytest 249 passed (+18 in `tests/test_mcp_envelope.py`), ruff check + format --check clean, mypy clean. Negative control: with `src/` reverted to origin/main all 18 new tests fail, restored they pass. Tests run the real server through an in-process `mcp.Client` (mcp 2.3).
