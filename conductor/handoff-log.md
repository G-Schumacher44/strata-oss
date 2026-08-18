# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-08-17 — feat/mcp-2x-migration

Commit: 1740642 (pre-merge branch anchor; squash-merge repo — post-squash resolve via
  `gh pr view <PR#> --json mergeCommit -q .mergeCommit.oid`)
Anchor semantics (squash-aware — this repo squash-merges, so branch SHAs never survive
  the merge): PRE-merge, 1740642 is the implementation commit on the PR branch. POST-squash,
  resolve the landed anchor deterministically via
  `gh pr view 22 --json mergeCommit -q .mergeCommit.oid` and use THAT for any HEAD check —
  no branch-SHA ancestry check is valid after a squash by construction. Canonical convention
  decision tracked in the repo issue "handoff anchors vs squash-merge".
Conductor Mode: slice (governing spec: conductor/slice-06-mcp-2x-migration.md)
Context Budget: low
Context Loaded: AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/index.md, handoff-log latest block, src/strata/mcp/server.py, tests/test_mcp_server.py.
Context Skipped: handoff-archive.md, docs/ (untouched).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: v0.1.8 tag is the post-merge publish trigger (operator/Koa on instruction).

**What changed:** migrated off the removed 1.x `mcp.server.fastmcp` API to mcp 2.x
(`mcp.server.mcpserver.MCPServer`), closing the follow-up named in the 0.1.7 handoff.

- `src/strata/mcp/server.py`: `FastMCP("strata")` + the `_mcp_server.version` workaround →
  `MCPServer("strata", version=_server_version())` — 2.x takes version as a first-class
  kwarg, so the #20 workaround retires cleanly. `@server.tool()` and `run(transport="stdio")`
  are API-compatible; no tool code changed.
- `pyproject.toml`: `mcp>=2,<3`. The upper bound STAYS as policy — an unbounded pin is what
  shipped a dead-on-arrival strata-mcp once (PR #18); lift `<3` only with a 3.x migration.
- `tests/test_mcp_server.py`: asserts the public `server.version` (2.x) instead of the 1.x
  private `_mcp_server.version`.
- Version triple-bumped 0.1.8 (pyproject, mcpb/manifest.json, mcpb shim pin) — tag guard
  verified consistent at 0.1.8.

**What was verified (fresh venv on mcp 2.x, resolver picked 2.0.0):**
- Full suite **108 passed**; ruff format+check clean.
- Live stdio handshake: `serverInfo {'name':'strata','version':'0.1.8'}`.
- Full MCP sequence (initialize → initialized → tools/list): **all 18 tools register**.
- API grounded by introspecting the installed 2.0.0 SDK (module layout, MCPServer init
  signature, tool/run signatures) — not from memory or docs.

**Exact Next Steps:**
1. Twin gate + Codex on the PR; operator/Koa merges on clean per standing order.
2. Tag `v0.1.8` post-merge; watch the release run (publish + .mcpb).
3. Post-publish: fresh-index smoke (install ==0.1.8, handshake reports 0.1.8, mcp
   resolves 2.x).
