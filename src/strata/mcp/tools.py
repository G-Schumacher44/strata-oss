"""Read-only MCP tool implementations over a resolved IRGraph."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from strata.ir.types import IRGraph
from strata.validation import validation_scope


def strata_query_field(graph: IRGraph, view: str, field: str) -> dict[str, Any]:
    node = graph.get_node(f"field:{view}.{field}")
    if node is None:
        return {"error": f"field not found: {view}.{field}"}
    return {
        "sql": node.attrs.get("sql"),
        "type": node.attrs.get("type"),
        "tags": node.attrs.get("tags", []),
        "source_file": node.source_file,
        "resolution_chain": node.attrs.get("resolution_chain", []),
    }


def strata_list_orphans(graph: IRGraph, kind: str = "all") -> list[dict[str, Any]]:
    if kind not in {"all", "view", "explore", "field"}:
        raise ValueError("kind must be one of: all, view, explore, field")
    orphans = graph.metadata.get("orphans", [])
    if kind == "all":
        return list(orphans)
    return [orphan for orphan in orphans if orphan.get("kind") == kind]


def strata_explore_deps(graph: IRGraph, explore: str, model: str) -> dict[str, Any]:
    node = graph.get_node(f"explore:{model}:{explore}")
    if node is None:
        return {"error": f"explore not found: {model}.{explore}"}
    joins = [
        {
            "name": join["name"],
            "view": join.get("from") or join["name"],
            "type": join.get("type"),
        }
        for join in node.attrs.get("joins", [])
    ]
    view_names = [node.attrs.get("base_view")] + [join["view"] for join in joins]
    field_count = sum(
        _field_count_for_view(graph, view_name) for view_name in view_names if view_name
    )
    return {
        "base_view": node.attrs.get("base_view"),
        "joins": joins,
        "resolution_chain": node.attrs.get("resolution_chain", []),
        "field_count": field_count,
    }


def strata_ir_status(graph: IRGraph) -> dict[str, Any]:
    return {
        "repo_path": graph.repo_path,
        "built_at": graph.built_at,
        "node_counts": graph.node_counts(),
        "edge_count": len(graph.edges),
        "cache_path": graph.cache_path,
    }


def strata_usage_summary(graph: IRGraph) -> dict[str, Any]:
    l1 = graph.metadata.get("l1", {})
    usage = l1.get("explore_usage", {})
    total_queries = sum(item.get("query_count", 0) for item in usage.values())
    return {
        "has_l1": bool(l1),
        "period": l1.get("period"),
        "explore_count": len(usage),
        "total_queries": total_queries,
        "dead_code_count": len(l1.get("dead_code", [])),
        "pdt_count": len(l1.get("pdt_ledger", [])),
        "unused_pdt_count": sum(
            1 for item in l1.get("pdt_ledger", []) if item.get("status") == "unused"
        ),
        "schema_drift_count": len(l1.get("schema_drift", [])),
    }


def strata_dead_code_register(graph: IRGraph) -> list[dict[str, Any]]:
    return list(graph.metadata.get("l1", {}).get("dead_code", []))


def strata_pdt_costs(graph: IRGraph) -> list[dict[str, Any]]:
    return list(graph.metadata.get("l1", {}).get("pdt_ledger", []))


def strata_schema_drift(graph: IRGraph) -> list[dict[str, Any]]:
    return list(graph.metadata.get("l1", {}).get("schema_drift", []))


def strata_validation_scope(
    graph: IRGraph, changed: Sequence[str | dict[str, Any]]
) -> dict[str, Any]:
    return validation_scope(graph, list(changed))


def strata_impact(graph: IRGraph, physical_table: str) -> dict[str, Any]:
    table_id = f"physical_table:{physical_table}"
    if table_id not in graph.nodes:
        return {"error": f"physical_table not found in IR: {physical_table}"}

    # Build reverse adjacency index once — O(E) — so inner loops are O(degree) not O(E)
    edges_by_target: dict[str, list] = {}
    for edge in graph.edges:
        edges_by_target.setdefault(edge.target, []).append(edge)

    views: set[str] = set()
    for edge in edges_by_target.get(table_id, []):
        if edge.relation == "view→physical_table":
            views.add(edge.source.removeprefix("view:"))
        elif edge.relation == "pdt→upstream":
            pdt = graph.get_node(edge.source)
            if pdt:
                views.add(pdt.name)

    explores: set[str] = set()
    fields: set[str] = set()
    for view in views:
        for edge in edges_by_target.get(f"view:{view}", []):
            if edge.relation in {"explore→base_view", "explore→joined_view"}:
                node = graph.get_node(edge.source)
                if node:
                    explores.add(f"{node.attrs.get('model')}.{node.name}")
        prefix = f"field:{view}."
        fields.update(
            node_id.removeprefix("field:") for node_id in graph.nodes if node_id.startswith(prefix)
        )
    return {
        "physical_table": physical_table,
        "views": sorted(views),
        "explores": sorted(explores),
        "fields": sorted(fields),
    }


def strata_find_field(graph: IRGraph, query: str, kind: str = "all") -> dict[str, Any]:
    """Search all views for fields matching a name fragment, SQL substring, or tag.

    Returns up to 50 matches. The `count` field is the number of returned matches,
    not the total possible matches; narrow the query or extend this cap for exhaustive output.
    """
    valid_kinds = {"all", "dimension", "measure", "filter", "parameter"}
    if kind not in valid_kinds:
        return {"error": f"kind must be one of: {', '.join(sorted(valid_kinds))}"}

    query_lower = query.lower()
    matches = []
    for node_id, node in graph.nodes.items():
        if not node_id.startswith("field:"):
            continue
        field_kind = node.attrs.get("field_kind", node.attrs.get("type", ""))
        if kind != "all" and field_kind != kind:
            continue
        name_hit = query_lower in node.name.lower()
        sql_hit = query_lower in str(node.attrs.get("sql", "")).lower()
        tag_hit = any(query_lower in str(t).lower() for t in node.attrs.get("tags", []))
        label_hit = query_lower in str(node.attrs.get("label", "")).lower()
        desc_hit = query_lower in str(node.attrs.get("description", "")).lower()
        group_hit = query_lower in str(node.attrs.get("group_label", "")).lower()
        if name_hit or sql_hit or tag_hit or label_hit or desc_hit or group_hit:
            matches.append(
                {
                    "view": node.attrs.get("view", node_id.split(":")[1].split(".")[0]),
                    "field": node.attrs.get("field_name", node.name.split(".")[-1]),
                    "type": field_kind,
                    "sql": node.attrs.get("sql"),
                    "label": node.attrs.get("label"),
                    "description": node.attrs.get("description"),
                    "source_file": node.source_file,
                    "source_line": node.attrs.get("source_line"),
                }
            )
        if len(matches) >= 50:
            break

    return {"query": query, "kind": kind, "matches": matches, "count": len(matches)}


def strata_view_sources(graph: IRGraph, model: str | None = None) -> dict[str, Any]:
    """List all views with their physical BQ table backing and field counts.

    Pass model= to restrict to views reachable from a specific model's explores.
    """
    # If model filter requested, collect views reachable from that model's explores
    scoped_views: set[str] | None = None
    if model:
        scoped_views = set()
        for node_id, node in graph.nodes.items():
            if node_id.startswith("explore:") and node.attrs.get("model") == model:
                base = node.attrs.get("base_view")
                if base:
                    scoped_views.add(base)
                for join in node.attrs.get("joins", []):
                    scoped_views.add(join.get("from") or join["name"])

    # Build forward edge index for view→physical_table lookups
    edges_by_source: dict[str, list] = {}
    for edge in graph.edges:
        edges_by_source.setdefault(edge.source, []).append(edge)

    views = []
    for node_id, node in graph.nodes.items():
        if not node_id.startswith("view:"):
            continue
        view_name = node.name
        if scoped_views is not None and view_name not in scoped_views:
            continue

        # Prefer edge-derived physical table; fall back to sql_table_name in body
        physical_table: str | None = None
        for edge in edges_by_source.get(node_id, []):
            if edge.relation == "view→physical_table":
                physical_table = edge.target.removeprefix("physical_table:")
                break
        if physical_table is None:
            body = node.attrs.get("body", {})
            physical_table = body.get("sql_table_name")

        views.append(
            {
                "name": view_name,
                "physical_table": physical_table,
                "field_count": _field_count_for_view(graph, view_name),
                "source_file": node.source_file,
                "source_line": node.attrs.get("source_line"),
                "orphan": node.attrs.get("orphan", False),
            }
        )

    views.sort(key=lambda v: v["name"])
    return {"model_filter": model, "views": views, "count": len(views)}


def strata_render_chart(spec_yaml: str, data_json: str, out_path: str) -> dict[str, str]:
    """Render a Vega-Lite spec (YAML or JSON string) + JSON data rows to an HTML file."""
    import json as _json

    resolved = Path(out_path).expanduser().resolve()
    allowed_roots = [
        (Path.home() / ".strata" / "output").resolve(),
        Path("/tmp").resolve(),
    ]
    if not any(str(resolved).startswith(str(r)) for r in allowed_roots):
        raise ValueError(f"out_path must be within ~/.strata/output/ or /tmp/. Got: {out_path!r}")

    try:
        import yaml as _yaml

        spec = _yaml.safe_load(spec_yaml)
    except ImportError:
        spec = _json.loads(spec_yaml)

    rows = _json.loads(data_json)
    from strata.viz.render import render_chart

    path = render_chart(spec, rows, resolved)
    return {"path": str(path), "status": "ok"}


def strata_chart_templates(charts_dir: str | Path) -> list[dict[str, str]]:
    """List available chart templates with mark type."""
    charts_dir = Path(charts_dir)
    templates = []
    for f in sorted(charts_dir.glob("*.yml")):
        content = f.read_text(encoding="utf-8")
        mark_m = re.search(r"^mark:\s*(\w+)", content, re.MULTILINE)
        templates.append(
            {
                "name": f.stem,
                "mark": mark_m.group(1) if mark_m else "?",
            }
        )
    return templates


def strata_list_skills(skills_dir: str | Path) -> list[dict[str, str]]:
    """List available skills with compact metadata — name, domain, mode, trigger only."""
    skills_dir = Path(skills_dir)
    skills = []
    for skill_file in sorted(skills_dir.rglob("SKILL.md")):
        content = skill_file.read_text(encoding="utf-8")
        meta = _parse_skill_meta(content)
        meta["name"] = skill_file.parent.name
        skills.append(meta)
    return skills


def strata_skill(skills_dir: str | Path, name: str) -> str:
    """Return full SKILL.md content for a given skill name. Pull-on-demand."""
    skills_dir = Path(skills_dir)
    for skill_file in skills_dir.rglob("SKILL.md"):
        if skill_file.parent.name == name:
            return skill_file.read_text(encoding="utf-8")
    return f"error: skill not found: {name}"


def strata_conductor_status(conductor_dir: str | Path) -> dict[str, Any]:
    """Return active slice, mode, and next steps. Capped for small context windows."""
    conductor_dir = Path(conductor_dir)
    result: dict[str, Any] = {}

    index_path = conductor_dir / "index.md"
    if index_path.exists():
        content = index_path.read_text(encoding="utf-8")
        m = re.search(r"Active slice[:\s=]+(.+)", content, re.IGNORECASE)
        result["active_slice"] = m.group(1).strip() if m else "none"

    handoff_path = conductor_dir / "handoff-log.md"
    if handoff_path.exists():
        content = handoff_path.read_text(encoding="utf-8")
        # Split on block headers — most recent block is first
        blocks = re.split(r"(?=^## Date:)", content, flags=re.MULTILINE)
        latest = next((b.strip() for b in blocks if b.strip().startswith("## Date:")), "")
        m = re.search(r"Exact Next Steps:\s*(.+?)(?:\n\n|$)", latest, re.DOTALL)
        if m:
            result["next_steps"] = m.group(1).strip()[:500]
        result["latest_handoff"] = "\n".join(latest.splitlines()[:20])

    return result


def _parse_skill_meta(content: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for key in ("domain", "mode", "complexity", "version"):
        m = re.search(rf"^{key}:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
        if m:
            meta[key] = m.group(1).strip()
    trigger_m = re.search(r"## Trigger\s*\n+([\s\S]+?)(?:\n\n---|\n##|$)", content)
    if trigger_m:
        bullets = re.findall(r"^[-*]\s+(.+)$", trigger_m.group(1), re.MULTILINE)
        if bullets:
            meta["trigger"] = bullets[0]
    return meta


def _field_count_for_view(graph: IRGraph, view: str) -> int:
    prefix = f"field:{view}."
    return sum(1 for node_id in graph.nodes if node_id.startswith(prefix))
