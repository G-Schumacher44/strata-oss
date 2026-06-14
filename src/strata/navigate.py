"""Navigator brief — deterministic ticket-anchor analysis over the IR.

Shared by the CLI (`strata query navigate`) and the MCP tool (`strata_navigate`),
so an agent gets the same brief in one call that the CLI builds in one pass.

`source_line` citations are read from `node.attrs["source_line"]`, which the IR build
populates (see `strata.ir.source_lines`). This module never reads raw LookML at request
time — it answers purely from the resolved/cached graph, per the MCP layer contract.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from strata.ir.types import IRGraph
from strata.mcp.tools import (
    strata_explore_deps,
    strata_find_field,
    strata_impact,
    strata_view_sources,
)

MAX_EXPLORES = 5


def build_navigate_brief(
    graph: IRGraph,
    anchor: str,
    model: str | None = None,
    ticket: str | None = None,
) -> dict[str, Any]:
    """Classify a ticket anchor, run the right lookups, and return a navigator brief.

    The brief names the views, explores, and fields an anchor touches, infers the change
    type from ticket text, and carries `source_file` + `source_line` (captured at IR build
    time) for each target so a downstream agent or developer can act without exploring the
    repo blind.
    """
    anchor_type = _classify_anchor(anchor)
    brief: dict[str, Any] = {"anchor": anchor, "anchor_type": anchor_type}

    views_hit: list[str] = []
    explores_hit: list[str] = []

    if anchor_type == "bq_table":
        result = strata_impact(graph, anchor)
        if "error" in result:
            return {"error": result["error"]}
        views_hit = result.get("views", [])
        explores_hit = result.get("explores", [])
        brief["bq_fields"] = result.get("fields", [])
        sources = strata_view_sources(graph, None)
        view_map = {v["name"]: v for v in sources["views"]}
        brief["views"] = [view_map.get(v, {"name": v}) for v in views_hit]

    elif anchor_type == "field":
        result = strata_find_field(graph, anchor, "all")
        matches = result.get("matches", [])
        if not matches:
            return {"error": f"No fields matching {anchor!r} found in IR"}
        brief["field_matches"] = matches
        views_hit = list({m["view"] for m in matches})

    else:
        name = _anchor_to_name(anchor, anchor_type)
        sources = strata_view_sources(graph, model)
        matched = [v for v in sources["views"] if name.lower() in v["name"].lower()]
        views_hit = [v["name"] for v in matched]
        explores_hit = _match_explores(graph, name)
        if matched:
            brief["views"] = matched
        # A single-token anchor can't be told apart from a bare field name. If it
        # matched no view or explore, resolve it as an unqualified field so that
        # documented field anchors (e.g. "user_id") are not silently empty.
        if not matched and not explores_hit:
            field_matches = strata_find_field(graph, name, "all").get("matches", [])
            if field_matches:
                brief["field_matches"] = field_matches
                views_hit = list({m["view"] for m in field_matches})
            else:
                return {"error": f"No view, explore, or field matching {anchor!r} found in IR"}

    if anchor_type == "explore" and not explores_hit:
        explores_hit = _match_explores(graph, _anchor_to_name(anchor, anchor_type))

    explore_details = []
    truncated_explores = len(explores_hit) > MAX_EXPLORES
    for ex in explores_hit[:MAX_EXPLORES]:
        model_name, explore_name = ex.split(".", 1)
        deps = strata_explore_deps(graph, explore_name, model_name)
        if "error" not in deps:
            node = graph.get_node(f"explore:{model_name}:{explore_name}")
            explore_details.append(
                {
                    "name": ex,
                    "base_view": deps.get("base_view"),
                    "field_count": deps.get("field_count"),
                    "joins": [j["name"] for j in deps.get("joins", [])],
                    "source_file": node.source_file if node else None,
                    "source_line": node.attrs.get("source_line") if node else None,
                }
            )
    if explore_details:
        brief["explores"] = explore_details

    if views_hit and anchor_type != "bq_table":
        sources = strata_view_sources(graph, model)
        view_map = {v["name"]: v for v in sources["views"]}
        brief["backing_tables"] = [view_map[v] for v in views_hit if v in view_map]

    if truncated_explores:
        brief["truncated"] = (
            f"Capped at {MAX_EXPLORES} of {len(explores_hit)} explores — pass model= to narrow."
        )

    if ticket:
        change_type = _infer_change_type(ticket)
        brief["change_type"] = change_type
        what: list[str] = []
        if change_type == "add_field" and views_hit:
            what.append(f"Edit view file for: {views_hit[0]}")
        elif change_type == "add_join" and explores_hit:
            what.append(f"Edit explore in model: {explores_hit[0].split('.')[0]}")
        elif change_type == "new_view":
            what.append("Create new .view.lkml file, then add join to relevant explore")
        brief["what_to_touch"] = what

    return brief


def _match_explores(graph: IRGraph, name: str) -> list[str]:
    hits = []
    for node_id in graph.nodes:
        if node_id.startswith("explore:") and name.lower() in node_id.lower():
            parts = node_id.split(":")
            if len(parts) == 3:
                hits.append(f"{parts[1]}.{parts[2]}")
    return hits


def _classify_anchor(anchor: str) -> str:
    if anchor.endswith((".view.lkml", ".model.lkml", ".explore.lkml")):
        return "file"
    parts = anchor.split(".")
    if len(parts) >= 3 and not anchor.endswith(".lkml"):
        return "bq_table"
    if len(parts) == 2:
        return "field"
    return "view"


def _anchor_to_name(anchor: str, anchor_type: str) -> str:
    if anchor_type == "file":
        for suffix in (".view.lkml", ".model.lkml", ".explore.lkml"):
            if anchor.endswith(suffix):
                return Path(anchor).name.replace(suffix, "")
    return anchor


def _infer_change_type(ticket: str) -> str:
    t = ticket.lower()
    if re.search(r"\b(add|new|create)\b.{0,30}\b(field|dimension|measure|metric|column)\b", t):
        return "add_field"
    if re.search(r"\b(add|new|create)\b.{0,20}\b(join|relationship)\b", t):
        return "add_join"
    if re.search(r"\b(add|new|create)\b.{0,20}\b(view|derived table|cte)\b", t):
        return "new_view"
    if re.search(r"\b(rename|move|migrate|refactor)\b", t):
        return "rename"
    if re.search(r"\b(remove|drop|delete|deprecate|clean up)\b", t):
        return "drop"
    return "unknown"
