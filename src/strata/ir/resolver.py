"""Resolve LookML extends/refinement chains into a trustworthy IR graph."""

from __future__ import annotations

import copy
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import networkx as nx

from strata.ir.types import IREdge, IRGraph, IRNode

FIELD_KEYS = ("dimension", "measure", "filter", "parameter")


class ResolutionError(ValueError):
    """Raised for unrecoverable resolution setup errors."""


def resolve_graph(raw_graph: IRGraph) -> IRGraph:
    """Resolve parsed LookML into a canonical graph."""

    parsed_files = raw_graph.metadata.get("parsed_files", [])
    resolved = IRGraph(
        repo_path=raw_graph.repo_path,
        built_at=datetime.now(UTC).isoformat(),
        cache_path=raw_graph.cache_path,
        metadata={"resolution_errors": [], "orphans": []},
    )
    models = _collect_models(parsed_files)
    view_defs, view_refinements = _collect_declarations(parsed_files, "view")
    explore_defs, explore_refinements = _collect_declarations(parsed_files, "explore")

    resolved_views = _resolve_named_objects(view_defs, view_refinements, "view")
    resolved_explores = _resolve_named_objects(explore_defs, explore_refinements, "explore")
    resolved.metadata["resolution_errors"].extend(resolved_views.errors)
    resolved.metadata["resolution_errors"].extend(resolved_explores.errors)

    _emit_models(resolved, models)
    _emit_views(resolved, resolved_views.objects)
    _emit_explores(resolved, models, resolved_explores.objects)
    _mark_orphans(resolved)
    return resolved


def build_resolved_graph(repo_path: str | Path) -> IRGraph:
    from strata.ir.builder import build_repo_graph
    from strata.ir.source_lines import attach_source_lines

    graph = resolve_graph(build_repo_graph(repo_path))
    attach_source_lines(graph)
    return graph


class _ResolvedSet:
    def __init__(self, objects: dict[str, dict[str, Any]], errors: list[dict[str, Any]]) -> None:
        self.objects = objects
        self.errors = errors


def _collect_models(parsed_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    models: list[dict[str, Any]] = []
    for parsed in parsed_files:
        if parsed.get("file_type") != "model":
            continue
        path = str(parsed["path"])
        name = Path(path).name.replace(".model.lkml", "")
        models.append(
            {"name": name, "source_file": path, "properties": parsed.get("properties", {})}
        )
    return models


def _collect_declarations(
    parsed_files: list[dict[str, Any]], kind: str
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    definitions: dict[str, dict[str, Any]] = {}
    refinements: dict[str, list[dict[str, Any]]] = {}
    for parsed in parsed_files:
        model_name = ""
        if parsed.get("file_type") == "model":
            model_name = Path(str(parsed["path"])).name.replace(".model.lkml", "")
        for declaration in parsed.get("declarations", []):
            if declaration.get("kind") != kind:
                continue
            name = str(declaration["name"])
            record = {
                "name": name,
                "kind": kind,
                "model": model_name,
                "source_file": declaration["source_file"],
                "body": copy.deepcopy(declaration.get("body", {})),
            }
            if declaration.get("refinement"):
                refinements.setdefault(name, []).append(record)
            elif name not in definitions:
                definitions[name] = record
            else:
                refinements.setdefault(name, []).append(record)
    return definitions, refinements


def _resolve_named_objects(
    definitions: dict[str, dict[str, Any]],
    refinements: dict[str, list[dict[str, Any]]],
    kind: str,
) -> _ResolvedSet:
    extends_graph = nx.DiGraph()
    for name, record in definitions.items():
        extends_graph.add_node(name)
        for base in _as_list(record["body"].get("extends")):
            extends_graph.add_edge(str(base), name)

    errors: list[dict[str, Any]] = []
    try:
        cycles = list(nx.simple_cycles(extends_graph))
    except nx.NetworkXException:
        cycles = []
    if cycles:
        for cycle in cycles:
            errors.append({"kind": kind, "type": "extends_cycle", "chain": cycle})

    resolved: dict[str, dict[str, Any]] = {}
    resolving: set[str] = set()

    def resolve_one(name: str) -> dict[str, Any]:
        if name in resolved:
            return copy.deepcopy(resolved[name])
        if name in resolving:
            errors.append(
                {"kind": kind, "type": "extends_cycle", "chain": sorted(resolving | {name})}
            )
            return _empty_object(name, kind)
        record = definitions.get(name)
        if record is None:
            errors.append({"kind": kind, "type": "missing_extends_target", "name": name})
            return _empty_object(name, kind)

        resolving.add(name)
        body: dict[str, Any] = {}
        chain: list[str] = []
        for base in _as_list(record["body"].get("extends")):
            base_name = str(base)
            parent = resolve_one(base_name)
            body = _merge_body(body, parent["body"])
            chain.extend(parent["resolution_chain"])

        body = _merge_body(body, record["body"])
        chain.append(name)
        sources = [record["source_file"]]
        for refinement in refinements.get(name, []):
            body = _merge_body(body, refinement["body"])
            chain.append(f"+{name}")
            sources.append(refinement["source_file"])

        resolving.remove(name)
        resolved[name] = {
            "name": name,
            "kind": kind,
            "model": record.get("model", ""),
            "source_file": record["source_file"],
            "source_files": sources,
            "body": body,
            "resolution_chain": _dedupe_keep_order(chain),
        }
        return copy.deepcopy(resolved[name])

    for name in sorted(definitions):
        resolve_one(name)
    return _ResolvedSet(resolved, errors)


def _emit_models(graph: IRGraph, models: list[dict[str, Any]]) -> None:
    for model in models:
        node_id = f"model:{model['name']}"
        props = model["properties"]
        graph.add_node(
            IRNode(
                id=node_id,
                kind="model",
                name=model["name"],
                source_file=model["source_file"],
                attrs=copy.deepcopy(props),
            )
        )
        connection = props.get("connection")
        if connection:
            connection_id = f"connection:{connection}"
            if connection_id not in graph.nodes:
                graph.add_node(
                    IRNode(
                        id=connection_id,
                        kind="connection",
                        name=str(connection),
                        source_file=model["source_file"],
                    )
                )
            graph.add_edge(IREdge(node_id, connection_id, "model→connection", model["source_file"]))
        for include in _as_list(props.get("include")):
            include_id = f"include:{model['name']}:{include}"
            graph.add_node(
                IRNode(
                    id=include_id,
                    kind="include",
                    name=str(include),
                    source_file=model["source_file"],
                )
            )
            graph.add_edge(IREdge(node_id, include_id, "model→include", model["source_file"]))


def _emit_views(graph: IRGraph, views: dict[str, dict[str, Any]]) -> None:
    for view in views.values():
        body = view["body"]
        view_id = f"view:{view['name']}"
        graph.add_node(
            IRNode(
                id=view_id,
                kind="view",
                name=view["name"],
                source_file=view["source_file"],
                attrs={
                    "body": copy.deepcopy(body),
                    "resolution_chain": view["resolution_chain"],
                    "source_files": view["source_files"],
                },
            )
        )
        sql_table = body.get("sql_table_name")
        if sql_table:
            sql_table = str(sql_table).strip().strip("`")
            table_id = f"physical_table:{sql_table}"
            if table_id not in graph.nodes:
                graph.add_node(IRNode(table_id, "physical_table", sql_table, view["source_file"]))
            graph.add_edge(IREdge(view_id, table_id, "view→physical_table", view["source_file"]))
        if "derived_table" in body:
            pdt_id = f"pdt:{view['name']}"
            graph.add_node(
                IRNode(
                    pdt_id,
                    "pdt",
                    view["name"],
                    view["source_file"],
                    {"derived_table": body["derived_table"]},
                )
            )
            graph.add_edge(IREdge(view_id, pdt_id, "view→pdt", view["source_file"]))
            for upstream in _sql_upstreams(str(body["derived_table"])):
                table_id = f"physical_table:{upstream}"
                if table_id not in graph.nodes:
                    graph.add_node(
                        IRNode(table_id, "physical_table", upstream, view["source_file"])
                    )
                graph.add_edge(IREdge(pdt_id, table_id, "pdt→upstream", view["source_file"]))
        for field_kind in FIELD_KEYS:
            for field_def in _as_list(body.get(field_kind)):
                if not isinstance(field_def, dict) or not field_def.get("name"):
                    continue
                field_id = f"field:{view['name']}.{field_def['name']}"
                graph.add_node(
                    IRNode(
                        id=field_id,
                        kind="field",
                        name=f"{view['name']}.{field_def['name']}",
                        source_file=view["source_file"],
                        attrs={
                            **copy.deepcopy(field_def),
                            "view": view["name"],
                            "field_name": field_def["name"],
                            "field_kind": field_kind,
                            "resolution_chain": view["resolution_chain"],
                        },
                    )
                )
                if field_def.get("sql"):
                    graph.add_edge(
                        IREdge(
                            field_id,
                            view_id,
                            "field→underlying_sql",
                            view["source_file"],
                            {"sql": field_def["sql"]},
                        )
                    )


def _emit_explores(
    graph: IRGraph,
    models: list[dict[str, Any]],
    explores: dict[str, dict[str, Any]],
) -> None:
    model_by_source = {model["source_file"]: model["name"] for model in models}
    for explore in explores.values():
        model = explore.get("model") or model_by_source.get(explore["source_file"], "")
        explore_id = f"explore:{model}:{explore['name']}"
        body = explore["body"]
        base_view = str(body.get("from") or explore["name"])
        joins = [
            join
            for join in _as_list(body.get("join"))
            if isinstance(join, dict) and join.get("name")
        ]
        graph.add_node(
            IRNode(
                id=explore_id,
                kind="explore",
                name=explore["name"],
                source_file=explore["source_file"],
                attrs={
                    "model": model,
                    "base_view": base_view,
                    "joins": copy.deepcopy(joins),
                    "body": copy.deepcopy(body),
                    "resolution_chain": explore["resolution_chain"],
                    "source_files": explore["source_files"],
                },
            )
        )
        graph.add_edge(
            IREdge(explore_id, f"view:{base_view}", "explore→base_view", explore["source_file"])
        )
        for join in joins:
            joined_view = str(join.get("from") or join["name"])
            graph.add_edge(
                IREdge(
                    explore_id,
                    f"view:{joined_view}",
                    "explore→joined_view",
                    explore["source_file"],
                    {
                        "name": join["name"],
                        "type": join.get("type"),
                        "relationship": join.get("relationship"),
                    },
                )
            )


def _mark_orphans(graph: IRGraph) -> None:
    used_views: set[str] = set()
    for edge in graph.edges:
        if edge.relation in {"explore→base_view", "explore→joined_view"} and edge.target.startswith(
            "view:"
        ):
            view_name = edge.target.removeprefix("view:")
            used_views.add(view_name)
            view = graph.nodes.get(edge.target)
            if view:
                used_views.update(
                    item.lstrip("+") for item in view.attrs.get("resolution_chain", [])
                )

    orphans: list[dict[str, Any]] = []
    for node in graph.nodes_by_kind("view"):
        if node.name not in used_views:
            orphan = {
                "id": node.id,
                "kind": node.kind,
                "name": node.name,
                "source_file": node.source_file,
                "reason": "view is not used as an explore base, join target, or resolved ancestor",
            }
            orphans.append(orphan)
            graph.nodes[node.id] = IRNode(
                node.id, node.kind, node.name, node.source_file, {**node.attrs, "orphan": True}
            )
        else:
            graph.nodes[node.id] = IRNode(
                node.id, node.kind, node.name, node.source_file, {**node.attrs, "orphan": False}
            )
    graph.metadata["orphans"] = orphans


def _merge_body(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in FIELD_KEYS or key == "join":
            merged[key] = _merge_named_lists(_as_list(merged.get(key)), _as_list(value))
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_body(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _merge_named_lists(base: list[Any], override: list[Any]) -> list[Any]:
    by_name: dict[str, Any] = {}
    order: list[str] = []
    for item in base + override:
        if not isinstance(item, dict) or "name" not in item:
            synthetic = str(len(order))
            by_name[synthetic] = copy.deepcopy(item)
            order.append(synthetic)
            continue
        name = str(item["name"])
        if name not in by_name:
            order.append(name)
            by_name[name] = {}
        if isinstance(by_name[name], dict):
            by_name[name] = _merge_body(by_name[name], item)
        else:
            by_name[name] = copy.deepcopy(item)
    return [by_name[name] for name in order]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _empty_object(name: str, kind: str) -> dict[str, Any]:
    return {
        "name": name,
        "kind": kind,
        "model": "",
        "source_file": "",
        "source_files": [],
        "body": {},
        "resolution_chain": [name],
    }


def _sql_upstreams(sql: str) -> list[str]:
    cte_names = set(re.findall(r"\b(\w+)\s+AS\s*\(", sql, flags=re.IGNORECASE))
    tables = set(re.findall(r"\b(?:from|join)\s+([A-Za-z_][\w.]+)", sql, flags=re.IGNORECASE))
    return sorted(tables - cte_names)
