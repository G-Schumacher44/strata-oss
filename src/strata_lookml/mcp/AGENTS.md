# MCP Layer — Read-Only Repo Brain

**Layer:** MCP server (exposes L0–L1 to the IDE)
**Full governance:** `GOVERNANCE.md`
**Authority:** `AGENTS.md` (root) → `intent.md` → `conductor/index.md` → active slice → this file

---

## What this layer is

A local stdio MCP server that exposes the pre-built IR (L0) and usage data (L1, Phase 2+)
as tools in the IDE (all read-only except `strata_render_chart`, which writes one HTML file
under `~/.strata/output/` or `/tmp/`). The team asks questions; this layer answers from the cache.
It never reads raw LookML files directly — it always goes through the IR.

## Hard constraints (non-negotiable)

- **stdio only.** No HTTP server, no TCP, no WebSocket. Transport is stdio exclusively.
  This is a local-only tool — no cloud dependency, no external endpoint.
- **Read-only tools only.** Every tool in this layer is a query over the IR cache.
  No tool may write to the LookML repo, to the IR cache during a live request, or to
  any external system.
- **Never call an LLM.** Tools return structured data. Synthesis is L2's job, not the
  MCP server's.
- **IR is the source of truth.** Never parse raw LookML files at request time. Load the
  cache on startup; rebuild if stale (default: > 5 min).
- **No writes on tool calls.** Cache rebuilds happen at startup only, not mid-request.

## Files in this layer

| File | Responsibility |
|---|---|
| `server.py` | stdio MCP entry point; loads IR cache on startup; routes tool calls |
| `tools.py` | Tool implementations — pure query functions over `IRGraph` |

## Tool contract

Tool names, parameters, descriptions and annotations are generated from the registered server —
see [docs/reference.md](../../../docs/reference.md#mcp-tools). Do not re-list signatures here; a
tool's docstring in `server.py` is the single source, and `tests/test_docs_consistency.py` fails
when the generated reference drifts.

Use `strata_list_skills()` first to pick a skill — compact metadata only, no token bloat.
Call `strata_skill(name)` only for the skill you intend to execute.

`strata_render_chart`: `spec_yaml` is a Vega-Lite YAML spec with data fields filled and
`data_json` is a JSON array of row objects. Output is a self-contained HTML file (Vega-Lite via
CDN, no install required).

Config via `STRATA_REPO_PATH` env var or `~/.strata/config.json`.
Optional fixture-backed L1 via `STRATA_USAGE_FIXTURE`.
Override toolkit root via `STRATA_TOOLKIT_PATH` (skills and chart templates resolve from here).

## Adding new tools

1. Add implementation in `tools.py` — pure function over `IRGraph`
2. Register in `server.py`, then run `python scripts/gen_reference.py` to refresh `docs/reference.md`
3. Add tests in `tests/test_mcp_tools.py` using fixture IR (not a live server)
4. Update `conductor/slice-*.md` if the tool is part of a slice deliverable

## What does NOT belong here

- IR parsing or graph building — that is `src/strata_lookml/ir/`
- LLM calls or synthesis — that is L2 (Phase 3+)
- HTTP transport or cloud endpoints — local stdio only
- Any tool that modifies state
