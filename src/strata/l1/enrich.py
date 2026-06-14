"""Join L0 IR with L1 usage and PDT cost facts."""

from __future__ import annotations

from datetime import UTC, datetime

from strata.ir.types import IRGraph
from strata.l1.types import (
    ContentReference,
    DeadCodeEvidence,
    ExploreUsage,
    PDTBuild,
    PDTLedgerRecord,
)


def enrich_graph(
    graph: IRGraph,
    explore_usage: list[ExploreUsage] | None = None,
    content_references: list[ContentReference] | None = None,
    pdt_builds: list[PDTBuild] | None = None,
    period: dict | None = None,
) -> IRGraph:
    if "l1" in graph.metadata:
        raise RuntimeError(
            "enrich_graph called twice on the same graph — enrich_graph is not idempotent"
        )
    usage = explore_usage or []
    builds = pdt_builds or []
    l1 = {
        "built_at": datetime.now(UTC).isoformat(),
        "period": period,
        "explore_usage": {item.key: item.to_dict() for item in usage},
        "content_references": [item.to_dict() for item in (content_references or [])],
        "pdt_builds": {item.view: item.to_dict() for item in builds},
    }
    l1["dead_code"] = [item.to_dict() for item in _dead_code(graph, usage, content_references)]
    l1["pdt_ledger"] = [item.to_dict() for item in _pdt_ledger(graph, builds)]
    graph.metadata["l1"] = l1
    return graph


def _dead_code(
    graph: IRGraph,
    usage: list[ExploreUsage],
    content: list[ContentReference] | None,
) -> list[DeadCodeEvidence]:
    usage_by_key = {item.key: item for item in usage}
    # None means content data was not provided — skip the content check entirely.
    # An explicit empty list means data was provided and no explores have content references.
    content_keys: set[str] | None = (
        {item.explore_key for item in content} if content is not None else None
    )
    records: list[DeadCodeEvidence] = []

    for orphan in graph.metadata.get("orphans", []):
        if orphan.get("kind") != "view":
            continue
        usage_reason = (
            "no explore/content usage references this resolved view"
            if content_keys is not None
            else "no explore references this resolved view; content references were not provided"
        )
        records.append(
            DeadCodeEvidence(
                id=f"dead:view:{orphan['name']}",
                kind="view",
                name=orphan["name"],
                source_file=orphan["source_file"],
                static_reason=orphan["reason"],
                usage_reason=usage_reason,
                evidence_ids=[orphan["id"], f"usage:view:{orphan['name']}"],
            )
        )

    dead_explore_keys: set[str] = set()
    for node in graph.nodes_by_kind("explore"):
        key = f"{node.attrs.get('model')}.{node.name}"
        item = usage_by_key.get(key)
        zero_queries = item is None or item.query_count == 0
        not_in_content = content_keys is not None and key not in content_keys
        if zero_queries and not_in_content:
            dead_explore_keys.add(key)
            usage_reason = (
                "no usage row present and no content references in L1 facts"
                if item is None
                else "zero queries and no content references in L1 facts"
            )
            records.append(
                DeadCodeEvidence(
                    id=f"dead:explore:{key}",
                    kind="explore",
                    name=key,
                    source_file=node.source_file,
                    static_reason="explore exists in resolved IR",
                    usage_reason=usage_reason,
                    evidence_ids=[node.id, f"usage:explore:{key}"],
                )
            )

    # Zombie views: views referenced exclusively by dead explores.
    # Distinct from orphan views (no explore reference at all) — these are structurally
    # connected but functionally unreachable because every explore backing them is dead.
    if dead_explore_keys:
        already_dead = {r.name for r in records if r.kind == "view"}
        for node in graph.nodes_by_kind("view"):
            if node.name in already_dead:
                continue
            explores = _explores_using_view(graph, node.name)
            if not explores:
                continue  # orphan — handled above
            if all(exp in dead_explore_keys for exp in explores):
                records.append(
                    DeadCodeEvidence(
                        id=f"dead:view:{node.name}",
                        kind="view",
                        name=node.name,
                        source_file=node.source_file,
                        static_reason="view exists in resolved IR",
                        usage_reason="all referencing explores have zero queries in L1 facts",
                        evidence_ids=[node.id] + [f"dead:explore:{exp}" for exp in explores],
                    )
                )

    return records


def _pdt_ledger(graph: IRGraph, builds: list[PDTBuild]) -> list[PDTLedgerRecord]:
    builds_by_view = {item.view: item for item in builds}
    records: list[PDTLedgerRecord] = []
    for pdt in graph.nodes_by_kind("pdt"):
        build = builds_by_view.get(pdt.name)
        used_by = _explores_using_view(graph, pdt.name)
        if build is None:
            records.append(
                PDTLedgerRecord(
                    view=pdt.name,
                    source_file=pdt.source_file,
                    build_count=0,
                    bytes_processed=0,
                    estimated_cost_usd=0.0,
                    used_by_explores=used_by,
                    status="missing_build_facts",
                    evidence_ids=[pdt.id],
                )
            )
            continue
        records.append(
            PDTLedgerRecord(
                view=pdt.name,
                source_file=pdt.source_file,
                build_count=build.build_count,
                bytes_processed=build.bytes_processed,
                estimated_cost_usd=build.estimated_cost_usd,
                used_by_explores=used_by,
                status="used" if used_by else "unused",
                evidence_ids=[pdt.id, f"pdt_build:{pdt.name}"],
            )
        )
    return records


def _explores_using_view(graph: IRGraph, view: str) -> list[str]:
    result: list[str] = []
    target = f"view:{view}"
    for edge in graph.edges:
        if edge.target != target or edge.relation not in {
            "explore→base_view",
            "explore→joined_view",
        }:
            continue
        node = graph.get_node(edge.source)
        if node and node.kind == "explore":
            result.append(f"{node.attrs.get('model')}.{node.name}")
    return sorted(result)
