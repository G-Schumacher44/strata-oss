"""Offline validation-scope planning over a resolved IR graph."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from strata.ir.types import IRGraph


@dataclass(frozen=True)
class ChangedObject:
    kind: str
    name: str

    @classmethod
    def from_value(cls, value: str | dict[str, Any]) -> ChangedObject:
        if isinstance(value, str):
            kind, _, name = value.partition(":")
            if not name:
                raise ValueError("changed object strings must use '<kind>:<name>'")
            return cls(kind=kind, name=name)
        return cls(kind=str(value["kind"]), name=str(value["name"]))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validation_scope(
    graph: IRGraph, changed: list[str | dict[str, Any] | ChangedObject]
) -> dict[str, Any]:
    changed_objects = [_coerce_changed(item) for item in changed]
    edges_by_target = _edges_by_target(graph)
    views: dict[str, set[str]] = {}
    unmatched: list[dict[str, str]] = []

    for item in changed_objects:
        impacted = _impacted_views(graph, edges_by_target, item)
        if not impacted:
            unmatched.append(item.to_dict())
            continue
        for view in impacted:
            views.setdefault(view, set()).add(f"{item.kind}:{item.name}")

    explores: dict[str, dict[str, Any]] = {}
    for view in sorted(views):
        for explore in _explores_using_view(graph, edges_by_target, view):
            entry = explores.setdefault(
                explore,
                {
                    "model": explore.split(".", 1)[0],
                    "explore": explore.split(".", 1)[1],
                    "impacted_views": set(),
                    "changed_inputs": set(),
                },
            )
            entry["impacted_views"].add(view)
            entry["changed_inputs"].update(views[view])

    return {
        "changed": [item.to_dict() for item in changed_objects],
        "explores": [
            {
                "model": item["model"],
                "explore": item["explore"],
                "impacted_views": sorted(item["impacted_views"]),
                "changed_inputs": sorted(item["changed_inputs"]),
            }
            for _, item in sorted(explores.items())
        ],
        "unmatched": sorted(unmatched, key=lambda item: (item["kind"], item["name"])),
    }


def _coerce_changed(value: str | dict[str, Any] | ChangedObject) -> ChangedObject:
    if isinstance(value, ChangedObject):
        return value
    return ChangedObject.from_value(value)


def _edges_by_target(graph: IRGraph) -> dict[str, list]:
    result: dict[str, list] = {}
    for edge in graph.edges:
        result.setdefault(edge.target, []).append(edge)
    return result


def _impacted_views(
    graph: IRGraph, edges_by_target: dict[str, list], item: ChangedObject
) -> set[str]:
    if item.kind == "view":
        return {item.name} if graph.get_node(f"view:{item.name}") else set()
    if item.kind in {"physical_table", "table"}:
        return _views_for_physical_table(graph, edges_by_target, item.name)
    return set()


def _views_for_physical_table(
    graph: IRGraph, edges_by_target: dict[str, list], table: str
) -> set[str]:
    table_id = f"physical_table:{table}"
    if table_id not in graph.nodes:
        return set()

    views: set[str] = set()
    for edge in edges_by_target.get(table_id, []):
        if edge.relation == "view→physical_table":
            views.add(edge.source.removeprefix("view:"))
        elif edge.relation == "pdt→upstream":
            pdt = graph.get_node(edge.source)
            if pdt:
                views.add(pdt.name)
    return views


def _explores_using_view(graph: IRGraph, edges_by_target: dict[str, list], view: str) -> list[str]:
    explores: set[str] = set()
    for edge in edges_by_target.get(f"view:{view}", []):
        if edge.relation not in {"explore→base_view", "explore→joined_view"}:
            continue
        node = graph.get_node(edge.source)
        if node and node.kind == "explore":
            explores.add(f"{node.attrs.get('model')}.{node.name}")
    return sorted(explores)
