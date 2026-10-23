"""Canonical IR data structures for Strata L0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx


@dataclass(frozen=True)
class IRNode:
    """A canonical LookML object in the resolved IR graph."""

    id: str
    kind: str
    name: str
    source_file: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "source_file": self.source_file,
            "attrs": self.attrs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IRNode:
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            name=str(data["name"]),
            source_file=str(data.get("source_file", "")),
            attrs=dict(data.get("attrs", {})),
        )


@dataclass(frozen=True)
class IREdge:
    """A typed relation between two IR nodes."""

    source: str
    target: str
    relation: str
    source_file: str = ""
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "source_file": self.source_file,
            "attrs": self.attrs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IREdge:
        return cls(
            source=str(data["source"]),
            target=str(data["target"]),
            relation=str(data["relation"]),
            source_file=str(data.get("source_file", "")),
            attrs=dict(data.get("attrs", {})),
        )


@dataclass
class IRGraph:
    """Serializable IR plus an in-memory NetworkX graph."""

    repo_path: str
    built_at: str
    cache_path: str = ""
    nodes: dict[str, IRNode] = field(default_factory=dict)
    edges: list[IREdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    graph: nx.DiGraph = field(default_factory=nx.DiGraph, repr=False)

    def add_node(self, node: IRNode) -> None:
        self.nodes[node.id] = node
        self.graph.add_node(node.id, **node.to_dict())

    def add_edge(self, edge: IREdge) -> None:
        self.edges.append(edge)
        self.graph.add_edge(
            edge.source,
            edge.target,
            relation=edge.relation,
            source_file=edge.source_file,
            attrs=edge.attrs,
        )

    def get_node(self, node_id: str) -> IRNode | None:
        return self.nodes.get(node_id)

    def nodes_by_kind(self, kind: str) -> list[IRNode]:
        return [node for node in self.nodes.values() if node.kind == kind]

    def node_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for node in self.nodes.values():
            counts[node.kind] = counts.get(node.kind, 0) + 1
        return dict(sorted(counts.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_path": self.repo_path,
            "built_at": self.built_at,
            "cache_path": self.cache_path,
            "metadata": self.metadata,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IRGraph:
        graph = cls(
            repo_path=str(data["repo_path"]),
            built_at=str(data["built_at"]),
            cache_path=str(data.get("cache_path", "")),
            metadata=dict(data.get("metadata", {})),
        )
        for node_data in data.get("nodes", []):
            graph.add_node(IRNode.from_dict(node_data))
        for edge_data in data.get("edges", []):
            graph.add_edge(IREdge.from_dict(edge_data))
        return graph
