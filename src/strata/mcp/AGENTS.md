# MCP Layer — Read-Only Repo Brain

**Layer:** MCP server (exposes L0–L1 to the IDE)
**Full governance:** `GOVERNANCE.md`
**Authority:** `AGENTS.md` (root) → `intent.md` → `conductor/index.md` → active slice → this file

---

## What this layer is

A local stdio MCP server that exposes the pre-built IR (L0) and usage data (L1, Phase 2+)
as read-only tools in the IDE. The team asks questions; this layer answers from the cache.
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

### IR / L1 tools (repo brain)
```
strata_query_field(view, field)      → sql, type, tags, source_file, resolution_chain
strata_list_orphans(kind="all")      → [{id, kind, name, source_file, reason}]
strata_explore_deps(explore, model)  → {base_view, joins, resolution_chain, field_count}
strata_ir_status()                   → {repo_path, built_at, node_counts, edge_count, cache_path}
strata_usage_summary()               → {has_l1, explore_count, total_queries, dead_code_count, ...}
strata_dead_code_register()          → [{id, kind, name, source_file, evidence_ids, ...}]
strata_pdt_costs()                   → [{view, build_count, estimated_cost_usd, status, ...}]
strata_schema_drift()                → [{view, field, drift_type, ...}]
strata_validation_scope(changed)     → {impacted_views, impacted_explores, impacted_fields}
strata_impact(physical_table)        → {physical_table, views, explores, fields}
strata_find_field(query, kind="all") → {query, kind, matches:[{view,field,type,sql,label,description,source_file,source_line}], count}
strata_view_sources(model=None)      → {model_filter, views:[{name,physical_table,field_count,source_file,source_line,orphan}], count}
strata_navigate(anchor, model=None,  → {anchor, anchor_type, views/explores/field_matches/bq_fields
              ticket=None)              with source_file:source_line, change_type, what_to_touch}
                                       Composite brief — one call replaces hand-orchestrating
                                       impact/find_field/view_sources/explore_deps.
```

### Skills tools (agent coordination)
```
strata_list_skills()                 → [{name, domain, mode, complexity, trigger}]
strata_skill(name)                   → full SKILL.md content (pull-on-demand)
strata_conductor_status()            → {active_slice, next_steps, latest_handoff}
```

Use `strata_list_skills()` first to pick a skill — compact metadata only, no token bloat.
Call `strata_skill(name)` only for the skill you intend to execute.

### Viz tools (chart rendering)
```
strata_chart_templates()             → [{name, mark}]  — bar|line|scatter|heatmap
strata_render_chart(spec_yaml,       → {path, status}
                    data_json,
                    out_path)
```

`spec_yaml` is a Vega-Lite YAML spec with data fields filled.
`data_json` is a JSON array of row objects.
Output is a self-contained HTML file (Vega-Lite via CDN, no install required).

Config via `STRATA_REPO_PATH` env var or `~/.strata/config.json`.
Optional fixture-backed L1 via `STRATA_USAGE_FIXTURE`.
Override toolkit root via `STRATA_TOOLKIT_PATH` (skills and chart templates resolve from here).

## Adding new tools

1. Add implementation in `tools.py` — pure function over `IRGraph`
2. Register in `server.py`
3. Add tests in `tests/test_mcp_tools.py` using fixture IR (not a live server)
4. Update `conductor/slice-*.md` if the tool is part of a slice deliverable

## What does NOT belong here

- IR parsing or graph building — that is `src/strata/ir/`
- LLM calls or synthesis — that is L2 (Phase 3+)
- HTTP transport or cloud endpoints — local stdio only
- Any tool that modifies state
