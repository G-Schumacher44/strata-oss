# Slice 06: mcp 2.x migration (MCPServer) — 0.1.8

Date: 2026-08-17
Status: review
Phase: distribution
Depends: slice-05 (audit remediation, merged as 0.1.7)

```yaml
conductor_mode: slice
context_budget: low
handoff_required: true
stable_tag_required: false
```

## Objective

Retire the last strata follow-up from 0.1.7: the server imported `mcp.server.fastmcp`,
which mcp 2.0 removed — forcing the defensive `mcp>=1.0,<2` pin (slice-05 / PR #18's
dead-on-arrival catch). Migrate to the 2.x API so the pin can advance.

Supersedes slice-05's "versions remain 0.1.7" constraint: that clause governed the
remediation release and closed with it; this slice's contract is the 0.1.8 triple-bump.

## Scope

`src/strata/mcp/server.py` (constructor + import only — zero tool code), `pyproject.toml`
pin + version, `tests/test_mcp_server.py` (public-attr assertion), mcpb triple-bump.
Layers: MCP surface only.

## Implementation Order

1. `FastMCP("strata")` + `_mcp_server.version` workaround → `MCPServer("strata",
   version=_server_version())` (2.x takes version first-class; retires #20's workaround).
2. Pin `mcp>=2,<3` — upper bound retained AS POLICY (unbounded is what broke fresh
   installs once); `<3` lifts only with a 3.x migration.
3. Test asserts public `server.version`.
4. Triple-bump 0.1.8; tag guard must pass.

## The Hard Constraint

The full MCP sequence (initialize → initialized → tools/list) must register ALL 18 tools
on a fresh venv that resolves mcp 2.x — API-compat assumptions proven by introspecting the
installed SDK, never assumed from 1.x docs.

## Acceptance Criteria

- [x] Suite green on a fresh venv resolving mcp 2.0.0 (108 passed)
- [x] Live stdio handshake reports the package version (0.1.8), not the SDK's
- [x] All 18 tools register via the full MCP sequence
- [x] Tag guard consistent at 0.1.8
- [ ] `v0.1.8` tag publishes; fresh-index smoke (install ==0.1.8 → handshake 0.1.8, mcp 2.x)
