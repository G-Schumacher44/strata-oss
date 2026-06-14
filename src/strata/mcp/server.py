"""Thin stdio MCP server for Strata repo-brain tools."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from strata.config import load_repo_path
from strata.ir.store import cache_age_seconds, load_ir, save_ir
from strata.ir.types import IRGraph
from strata.mcp.tools import (
    strata_chart_templates as query_chart_templates,
)
from strata.mcp.tools import (
    strata_conductor_status as query_conductor_status,
)
from strata.mcp.tools import (
    strata_dead_code_register as query_dead_code_register,
)
from strata.mcp.tools import (
    strata_explore_deps as query_explore_deps,
)
from strata.mcp.tools import (
    strata_find_field as query_find_field,
)
from strata.mcp.tools import (
    strata_impact as query_impact,
)
from strata.mcp.tools import (
    strata_ir_status as query_ir_status,
)
from strata.mcp.tools import (
    strata_list_orphans as query_list_orphans,
)
from strata.mcp.tools import (
    strata_list_skills as query_list_skills,
)
from strata.mcp.tools import (
    strata_pdt_costs as query_pdt_costs,
)
from strata.mcp.tools import (
    strata_query_field as query_field,
)
from strata.mcp.tools import (
    strata_render_chart as query_render_chart,
)
from strata.mcp.tools import (
    strata_schema_drift as query_schema_drift,
)
from strata.mcp.tools import (
    strata_skill as query_skill,
)
from strata.mcp.tools import (
    strata_usage_summary as query_usage_summary,
)
from strata.mcp.tools import (
    strata_validation_scope as query_validation_scope,
)
from strata.mcp.tools import (
    strata_view_sources as query_view_sources,
)
from strata.navigate import build_navigate_brief
from strata.pipeline import build_graph

CACHE_MAX_AGE_SECONDS = 300


def load_configured_graph() -> IRGraph:
    repo_path = _repo_path()
    cache_path = _cache_path(repo_path)
    age = cache_age_seconds(cache_path)
    if age is not None and age < CACHE_MAX_AGE_SECONDS:
        return load_ir(cache_path)
    graph = build_graph(repo_path, _usage_fixture(), _schema_fixture())
    save_ir(graph, cache_path)
    return graph


def create_server(graph: IRGraph | None = None) -> FastMCP:
    ir_graph = graph or load_configured_graph()
    server = FastMCP("strata")

    @server.tool()
    def strata_query_field(view: str, field: str) -> dict[str, Any]:
        return query_field(ir_graph, view, field)

    @server.tool()
    def strata_list_orphans(kind: str = "all") -> list[dict[str, Any]]:
        return query_list_orphans(ir_graph, kind)

    @server.tool()
    def strata_explore_deps(explore: str, model: str) -> dict[str, Any]:
        return query_explore_deps(ir_graph, explore, model)

    @server.tool()
    def strata_ir_status() -> dict[str, Any]:
        return query_ir_status(ir_graph)

    @server.tool()
    def strata_usage_summary() -> dict[str, Any]:
        return query_usage_summary(ir_graph)

    @server.tool()
    def strata_dead_code_register() -> list[dict[str, Any]]:
        return query_dead_code_register(ir_graph)

    @server.tool()
    def strata_pdt_costs() -> list[dict[str, Any]]:
        return query_pdt_costs(ir_graph)

    @server.tool()
    def strata_schema_drift() -> list[dict[str, Any]]:
        return query_schema_drift(ir_graph)

    @server.tool()
    def strata_validation_scope(changed: list[str | dict[str, Any]]) -> dict[str, Any]:
        """Determine blast radius for changes (impacted_views, impacted_explores, impacted_fields)."""
        return query_validation_scope(ir_graph, changed)

    @server.tool()
    def strata_impact(physical_table: str) -> dict[str, Any]:
        """Get the downstream impact of a physical table (physical_table, views, explores, fields)."""
        return query_impact(ir_graph, physical_table)

    @server.tool()
    def strata_find_field(
        query: str, kind: Literal["all", "dimension", "measure", "filter", "parameter"] = "all"
    ) -> dict[str, Any]:
        """Search for fields matching a query string across all views (query, kind, matches, count)."""
        return query_find_field(ir_graph, query, kind)

    @server.tool()
    def strata_view_sources(model: str | None = None) -> dict[str, Any]:
        """List views and their resolved physical tables (model_filter, views, count)."""
        return query_view_sources(ir_graph, model)

    @server.tool()
    def strata_navigate(
        anchor: str, model: str | None = None, ticket: str | None = None
    ) -> dict[str, Any]:
        """Classify a ticket anchor and return a full navigator brief in one call.

        anchor: BQ table, field name, view, explore, or .lkml filename.
        Returns the views/explores/fields it touches with source_file:source_line
        citations, plus an inferred change type and what-to-touch list when ticket is set.
        """
        return build_navigate_brief(ir_graph, anchor, model, ticket)

    skills_dir = _skills_dir()
    conductor_dir = _conductor_dir()

    @server.tool()
    def strata_list_skills() -> list[dict[str, str]]:
        """List available skills (name, domain, mode, complexity, trigger)."""
        return query_list_skills(skills_dir)

    @server.tool()
    def strata_skill(name: str) -> str:
        """Get the full SKILL.md content for a specific skill."""
        return query_skill(skills_dir, name)

    @server.tool()
    def strata_conductor_status() -> dict[str, Any]:
        """Get the current Conductor workflow status (active_slice, next_steps, latest_handoff)."""
        return query_conductor_status(conductor_dir)

    charts_dir = _charts_dir()

    @server.tool()
    def strata_chart_templates() -> list[dict[str, str]]:
        """List available Vega-Lite chart templates (name, mark)."""
        return query_chart_templates(charts_dir)

    @server.tool()
    def strata_render_chart(spec_yaml: str, data_json: str, out_path: str) -> dict[str, str]:
        """Render a chart using a Vega-Lite template and JSON data (path, status)."""
        return query_render_chart(spec_yaml, data_json, out_path)

    return server


def main() -> None:
    import sys

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


def _cache_path(repo_path: Path) -> Path:
    env_path = os.environ.get("STRATA_CACHE_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return repo_path / "strata_ir.db"


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
