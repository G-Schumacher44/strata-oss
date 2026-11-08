"""Thin stdio MCP server for Strata repo-brain tools."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from strata_lookml.config import load_cache_path, load_repo_path
from strata_lookml.ir.types import IRGraph
from strata_lookml.mcp.tools import (
    FIND_FIELD_DEFAULT_LIMIT,
    FIND_FIELD_MAX_LIMIT,
    l1_list_envelope,
    list_envelope,
)
from strata_lookml.mcp.tools import (
    strata_chart_templates as query_chart_templates,
)
from strata_lookml.mcp.tools import (
    strata_conductor_status as query_conductor_status,
)
from strata_lookml.mcp.tools import (
    strata_dead_code_register as query_dead_code_register,
)
from strata_lookml.mcp.tools import (
    strata_explore_deps as query_explore_deps,
)
from strata_lookml.mcp.tools import (
    strata_find_field as query_find_field,
)
from strata_lookml.mcp.tools import (
    strata_impact as query_impact,
)
from strata_lookml.mcp.tools import (
    strata_ir_status as query_ir_status,
)
from strata_lookml.mcp.tools import (
    strata_list_orphans as query_list_orphans,
)
from strata_lookml.mcp.tools import (
    strata_list_skills as query_list_skills,
)
from strata_lookml.mcp.tools import (
    strata_pdt_costs as query_pdt_costs,
)
from strata_lookml.mcp.tools import (
    strata_query_field as query_field,
)
from strata_lookml.mcp.tools import (
    strata_render_chart as query_render_chart,
)
from strata_lookml.mcp.tools import (
    strata_schema_drift as query_schema_drift,
)
from strata_lookml.mcp.tools import (
    strata_skill as query_skill,
)
from strata_lookml.mcp.tools import (
    strata_usage_summary as query_usage_summary,
)
from strata_lookml.mcp.tools import (
    strata_validation_scope as query_validation_scope,
)
from strata_lookml.mcp.tools import (
    strata_view_sources as query_view_sources,
)
from strata_lookml.navigate import build_navigate_brief
from strata_lookml.pipeline import load_or_build

CACHE_MAX_AGE_SECONDS = 300


def _server_version() -> str:
    try:
        return pkg_version("strata-lookml")
    except PackageNotFoundError:
        # Editable/dev checkout without an installed distribution record.
        return "0.0.0-dev"


def load_configured_graph() -> IRGraph:
    repo_path = _repo_path()
    return load_or_build(
        repo_path,
        _usage_fixture(),
        _schema_fixture(),
        load_cache_path(repo_path),
        CACHE_MAX_AGE_SECONDS,
    )


# Tool annotations are advisory hints (MCP spec: clients treat them as untrusted unless the
# server is trusted). Every tool is read-only except the sandboxed chart renderer, which
# writes one HTML file under ~/.strata/output or /tmp and may overwrite an existing file there.
# (The IR cache write in load_configured_graph happens at server start, not in a tool call.)
_READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
_RENDER_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False
)


_INSTRUCTIONS = """\
Strata analyzes a LookML repo (views, explores, fields, physical tables) and, when usage and
schema facts are loaded, flags dead code, unused/zombie PDTs and schema drift. Read-only except
strata_render_chart.
- Start with strata_ir_status (what repo is loaded) and strata_usage_summary (which checks ran).
- Ticket or question about one thing: strata_navigate with the anchor (table, field, view,
  explore or .lkml file); strata_find_field to search field names by fragment.
- Change impact: strata_validation_scope for edited files/objects, strata_impact for a table.
- List tools return one object {"items": [...], "count": N}. L1 tools (dead code, PDT costs,
  schema drift) also return usage_checked / schema_checked: false means the check did not run
  and an empty list is NOT a clean result; the hint names the env var to set
  (STRATA_USAGE_FIXTURE / STRATA_SCHEMA_FIXTURE) before restarting the server.
- Failures come back as isError with a message and a hint; read the hint before retrying.
- strata_list_skills / strata_skill return playbooks; strata_render_chart writes one HTML file
  under ~/.strata/output or /tmp.
"""


_View = Annotated[str, Field(description="View name as written in LookML.", examples=["orders"])]
_Explore = Annotated[str, Field(description="Explore name.", examples=["order_items"])]
_ModelName = Annotated[str, Field(description="LookML model name (the .model.lkml file stem).")]


def create_server(graph: IRGraph | None = None) -> MCPServer:
    ir_graph = graph or load_configured_graph()
    # mcp 2.x: MCPServer replaced FastMCP (removed in 2.0) and takes `version` as a
    # first-class kwarg — retiring the 1.x `_mcp_server.version` workaround from #20.
    server = MCPServer("strata", version=_server_version(), instructions=_INSTRUCTIONS)

    @server.tool(title="Query Field", annotations=_READ_ONLY)
    def strata_query_field(
        view: _View,
        field: Annotated[str, Field(description="Field name within the view.", examples=["id"])],
    ) -> dict[str, Any]:
        """Get one field's resolved definition (sql, type, tags, source_file, resolution_chain). Errors with not_found if the view.field pair is absent; use strata_find_field to locate a field by fragment."""
        return query_field(ir_graph, view, field)

    @server.tool(title="List Orphans", annotations=_READ_ONLY)
    def strata_list_orphans(
        kind: Annotated[
            Literal["all", "view"],
            Field(
                description="Only 'view' is meaningful: orphan explores/fields are not detected."
            ),
        ] = "all",
    ) -> dict[str, Any]:
        """List orphan views (no explore uses them as base, join, or extends ancestor). Returns {items, count}."""
        return list_envelope(query_list_orphans(ir_graph, kind))

    @server.tool(title="Explore Dependencies", annotations=_READ_ONLY)
    def strata_explore_deps(explore: _Explore, model: _ModelName) -> dict[str, Any]:
        """Get an explore's base view, joins (name, view, type), resolution_chain, and total field_count. Both explore and model are required; errors with not_found if the pair does not exist (strata_navigate finds an explore by name)."""
        return query_explore_deps(ir_graph, explore, model)

    @server.tool(title="IR Status", annotations=_READ_ONLY)
    def strata_ir_status() -> dict[str, Any]:
        """Summarize the loaded IR (repo_path, built_at, node_counts, edge_count, cache_path). Call first to confirm which repo is loaded."""
        return query_ir_status(ir_graph)

    @server.tool(title="Usage Summary", annotations=_READ_ONLY)
    def strata_usage_summary() -> dict[str, Any]:
        """Summarize L1 usage facts and which checks ran: usage_checked / schema_checked (has_l1 is deprecated), period, query totals, explore population (ir_explore_count, active/dead counts), dead-code/PDT/zombie/drift counts. A zero count means 'nothing found' only when its check ran; hint names the fixture env var to set otherwise."""
        return query_usage_summary(ir_graph)

    @server.tool(title="Dead Code Register", annotations=_READ_ONLY)
    def strata_dead_code_register() -> dict[str, Any]:
        """List dead explores (zero queries, no content refs) and dead views (orphan, or every consumer dead). Returns {items, count, usage_checked, hint?}. Needs usage facts (STRATA_USAGE_FIXTURE); when it was not loaded usage_checked is false with a hint naming the env var, and an empty list means 'not checked'."""
        return l1_list_envelope(ir_graph, query_dead_code_register(ir_graph), "usage")

    @server.tool(title="PDT Costs", annotations=_READ_ONLY)
    def strata_pdt_costs() -> dict[str, Any]:
        """List PDT builds, bytes, estimated USD cost, consumers, and status (used/unused/zombie/missing_build_facts). Returns {items, count, usage_checked, hint?}. Needs usage facts (STRATA_USAGE_FIXTURE); when it was not loaded usage_checked is false with a hint naming the env var, and an empty list means 'not checked'."""
        return l1_list_envelope(ir_graph, query_pdt_costs(ir_graph), "usage")

    @server.tool(title="Schema Drift", annotations=_READ_ONLY)
    def strata_schema_drift() -> dict[str, Any]:
        """List tables and field-referenced columns missing from BigQuery schema facts. Returns {items, count, schema_checked, hint?}. Needs schema facts (STRATA_SCHEMA_FIXTURE); when it was not loaded schema_checked is false with a hint naming the env var, and an empty list means 'not checked'."""
        return l1_list_envelope(ir_graph, query_schema_drift(ir_graph), "schema")

    @server.tool(title="Validation Scope", annotations=_READ_ONLY)
    def strata_validation_scope(
        changed: Annotated[
            list[str | dict[str, Any]],
            Field(
                description="Changed objects, each '<kind>:<name>' (kinds: view, explore, "
                'field, ...) or {"kind": ..., "name": ...}.',
                examples=[["view:orders", "field:orders.id"]],
                min_length=1,
            ),
        ],
    ) -> dict[str, Any]:
        """Determine blast radius for changes (impacted_views, impacted_explores, impacted_fields). Malformed entries fail with invalid_input naming the accepted '<kind>:<name>' form."""
        return query_validation_scope(ir_graph, changed)

    @server.tool(title="Table Impact", annotations=_READ_ONLY)
    def strata_impact(
        physical_table: Annotated[
            str,
            Field(
                description="Table exactly as written in sql_table_name (strata_view_sources "
                "lists them).",
                examples=["analytics.orders"],
            ),
        ],
    ) -> dict[str, Any]:
        """Get the downstream impact of a physical table (physical_table, views, explores, fields). Errors with not_found if the table is not in the IR."""
        return query_impact(ir_graph, physical_table)

    @server.tool(title="Find Field", annotations=_READ_ONLY)
    def strata_find_field(
        query: Annotated[
            str,
            Field(
                description="Fragment matched against field name, label, description, group "
                "label, tags and SQL (case-insensitive).",
                examples=["revenue"],
                min_length=2,
            ),
        ],
        kind: Annotated[
            Literal["all", "dimension", "measure", "filter", "parameter"],
            Field(description="Restrict to one field kind."),
        ] = "all",
        limit: Annotated[
            int,
            Field(
                description="Max matches returned (default 50, max 200); truncated=true means more exist.",
                ge=1,
                le=FIND_FIELD_MAX_LIMIT,
            ),
        ] = FIND_FIELD_DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """Search for fields matching a query string across all views (query, kind, matches, count, truncated). count is the number returned, not the total."""
        return query_find_field(ir_graph, query, kind, limit)

    @server.tool(title="View Sources", annotations=_READ_ONLY)
    def strata_view_sources(
        model: Annotated[
            str | None,
            Field(description="Restrict to views reachable from this model's explores."),
        ] = None,
    ) -> dict[str, Any]:
        """List views and their resolved physical tables (model_filter, views, count). Errors with not_found, listing known models, if model is unknown."""
        return query_view_sources(ir_graph, model)

    @server.tool(title="Navigate Ticket Anchor", annotations=_READ_ONLY)
    def strata_navigate(
        anchor: Annotated[
            str,
            Field(
                description="BQ table, field name, view, explore, or .lkml filename.",
                examples=["orders", "analytics.orders", "orders.view.lkml"],
            ),
        ],
        model: Annotated[
            str | None, Field(description="Disambiguate an explore name shared across models.")
        ] = None,
        ticket: Annotated[
            str | None,
            Field(
                description="Ticket text; when set, adds an inferred change type and a what-to-touch list."
            ),
        ] = None,
    ) -> dict[str, Any]:
        """Classify a ticket anchor and return a full navigator brief in one call.

        Returns the views/explores/fields it touches with source_file:source_line
        citations, plus an inferred change type and what-to-touch list when ticket is set.
        An anchor that matches nothing returns not_found with a hint toward strata_find_field.
        """
        return build_navigate_brief(ir_graph, anchor, model, ticket)

    skills_dir = _skills_dir()
    conductor_dir = _conductor_dir()

    @server.tool(title="List Skills", annotations=_READ_ONLY)
    def strata_list_skills() -> dict[str, Any]:
        """List available skills (name, domain, mode, complexity, trigger). Returns {items, count}; fetch one with strata_skill."""
        return list_envelope(query_list_skills(skills_dir))

    @server.tool(title="Get Skill", annotations=_READ_ONLY)
    def strata_skill(
        name: Annotated[
            str,
            Field(
                description="Skill name from strata_list_skills.", examples=["bq_query_guardrail"]
            ),
        ],
    ) -> str:
        """Get the full SKILL.md content for a specific skill. Unknown names fail with not_found listing the available skills."""
        return query_skill(skills_dir, name)

    @server.tool(title="Conductor Status", annotations=_READ_ONLY)
    def strata_conductor_status() -> dict[str, Any]:
        """Get the current Conductor workflow status (active_slice, next_steps, latest_handoff) from the governed repo's conductor/ directory; keys are omitted when the files are absent."""
        return query_conductor_status(conductor_dir)

    charts_dir = _charts_dir()

    @server.tool(title="Chart Templates", annotations=_READ_ONLY)
    def strata_chart_templates() -> dict[str, Any]:
        """List available Vega-Lite chart templates (name, mark). Returns {items, count}."""
        return list_envelope(query_chart_templates(charts_dir))

    @server.tool(title="Render Chart", annotations=_RENDER_ANNOTATIONS)
    def strata_render_chart(
        spec_yaml: Annotated[
            str,
            Field(
                description="Vega-Lite spec as YAML or JSON (a mapping); start from a "
                "strata_chart_templates template."
            ),
        ],
        data_json: Annotated[
            str,
            Field(
                description="JSON array of row objects. Every field named in the spec's "
                "encoding must be a key in the rows.",
                examples=['[{"month": "2026-01", "total": 12}]'],
            ),
        ],
        out_path: Annotated[
            str,
            Field(
                description="Output file, must end in .html and sit under ~/.strata/output/ or "
                "/tmp/ (sandboxed; symlinks refused; an existing file is overwritten).",
                examples=["/tmp/chart.html"],
            ),
        ],
    ) -> dict[str, str]:
        """Render a chart from a Vega-Lite spec and JSON rows to a self-contained HTML file (returns path, status). Writes (and may overwrite) one file, only under ~/.strata/output/ or /tmp/; an out_path outside that sandbox or malformed spec/data fails with invalid_input."""
        return query_render_chart(spec_yaml, data_json, out_path)

    return server


_USAGE = """\
usage: strata-mcp [-h]

Strata's MCP server over stdio: read-only LookML analysis tools plus a sandboxed chart
renderer. An MCP client (Claude, Cursor, VS Code, ...) launches this command; it speaks
JSON-RPC on stdin/stdout and takes no arguments.

Configuration (environment):
  STRATA_REPO_PATH        LookML repo to analyze (else ~/.strata/config.json, else cwd)
  STRATA_USAGE_FIXTURE    usage facts JSON for offline L1 enrichment
  STRATA_SCHEMA_FIXTURE   BigQuery schema facts JSON for drift checks
  STRATA_CACHE_PATH       IR cache file (default: ~/.strata/cache/<repo>-<hash>.db)

Check the setup first with `strata mcp validate`; print client config with `strata mcp config`.
"""


def main(argv: list[str] | None = None) -> None:
    import sys

    args = sys.argv[1:] if argv is None else argv
    if any(arg in ("-h", "--help") for arg in args):
        # Print usage and exit before building the graph or opening the stdio transport.
        sys.stdout.write(_USAGE)
        return

    sys.stderr.write("Starting Strata MCP server...\n")
    server = create_server()
    sys.stderr.write("Server initialized. Running stdio transport...\n")
    server.run(transport="stdio")


def _skills_dir() -> Path:
    env = os.environ.get("STRATA_SKILLS_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "skills"


def _charts_dir() -> Path:
    env = os.environ.get("STRATA_CHARTS_PATH")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "viz" / "charts"


def _conductor_dir() -> Path:
    env = os.environ.get("STRATA_CONDUCTOR_PATH")
    if env:
        return Path(env).expanduser().resolve()
    # conductor lives in the governed repo, not the package
    repo = _repo_path()
    return repo / "conductor"


def _repo_path() -> Path:
    return load_repo_path()


def _usage_fixture() -> Path | None:
    env_path = os.environ.get("STRATA_USAGE_FIXTURE")
    if not env_path:
        return None
    return Path(env_path).expanduser().resolve()


def _schema_fixture() -> Path | None:
    env_path = os.environ.get("STRATA_SCHEMA_FIXTURE")
    if not env_path:
        return None
    return Path(env_path).expanduser().resolve()


if __name__ == "__main__":
    main()
