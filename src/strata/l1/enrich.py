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
    dead_code_records = _dead_code(graph, usage, content_references)
    l1["dead_code"] = [item.to_dict() for item in dead_code_records]
    dead_explore_keys = {item.name for item in dead_code_records if item.kind == "explore"}
    l1["pdt_ledger"] = [item.to_dict() for item in _pdt_ledger(graph, builds, dead_explore_keys)]
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
        consumers_by_view = view_consumer_map(graph)  # built once, not per view
        for node in graph.nodes_by_kind("view"):
            if node.name in already_dead:
                continue
            explores = consumers_by_view.get(node.name, [])
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


def _pdt_ledger(
    graph: IRGraph, builds: list[PDTBuild], dead_explore_keys: set[str]
) -> list[PDTLedgerRecord]:
    builds_by_view = {item.view: item for item in builds}
    # DIRECT consumers only: a PDT is per-view materialization — an explore targeting a
    # child view queries the child's own pdt:<view> node, never the parent's (round 4).
    consumers_by_view = direct_view_consumers(graph)  # built once, not per pdt
    records: list[PDTLedgerRecord] = []
    for pdt in graph.nodes_by_kind("pdt"):
        build = builds_by_view.get(pdt.name)
        used_by = consumers_by_view.get(pdt.name, [])
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
        evidence_ids = [pdt.id, f"pdt_build:{pdt.name}"]
        if not used_by:
            status = "unused"
        elif all(exp in dead_explore_keys for exp in used_by):
            # Zombie: real build facts, real consumers, but every consuming explore is
            # itself dead — the PDT keeps rebuilding on schedule to serve nobody.
            # The verdict rests on those explores' dead-code register entries, so cite
            # them (same `dead:explore:` convention the dead-views records use) — a
            # zombie whose evidence trail omits WHY its consumers are dead would be
            # an un-auditable verdict in a tool whose whole contract is dual evidence.
            status = "zombie"
            evidence_ids += [f"dead:explore:{exp}" for exp in used_by]
        else:
            status = "used"
        records.append(
            PDTLedgerRecord(
                view=pdt.name,
                source_file=pdt.source_file,
                build_count=build.build_count,
                bytes_processed=build.bytes_processed,
                estimated_cost_usd=build.estimated_cost_usd,
                used_by_explores=used_by,
                status=status,
                evidence_ids=evidence_ids,
            )
        )
    return records


def direct_view_consumers(graph: IRGraph) -> dict[str, list[str]]:
    """Explores that DIRECTLY target each view (base or join edges only).

    This is the right question for anything tied to a specific view's own
    materialization — above all the PDT ledger: the resolver emits a separate
    `pdt:<view>` node per PDT-bearing view, so an explore targeting a CHILD view
    queries the child's own materialization, never the parent's. Crediting inherited
    consumers to a parent's PDT would hide a genuinely unused/zombie parent PDT behind
    a live child (PR #25 Codex round 4). Keys are bare view names; values sorted,
    model-qualified explore keys.
    """
    direct: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.relation not in {"explore→base_view", "explore→joined_view"}:
            continue
        if not edge.target.startswith("view:"):
            continue
        node = graph.get_node(edge.source)
        if node and node.kind == "explore":
            direct.setdefault(edge.target.removeprefix("view:"), []).append(
                f"{node.attrs.get('model')}.{node.name}"
            )
    return {name: sorted(set(keys)) for name, keys in direct.items()}


def view_consumer_map(graph: IRGraph) -> dict[str, list[str]]:
    """Ancestry-aware reachability: which explores keep this view ALIVE.

    An explore targeting a child view reaches every ancestor in the child's
    `resolution_chain` — the resolver's `_mark_orphans` treats ancestors as used, so
    orphan/zombie-VIEW verdicts and the dashboard's view panel share this derivation
    (PR #25 rounds 1–2). NOT for PDT consumer questions — those are per-materialization
    and use `direct_view_consumers` (round 4). Two questions, two maps, one shared
    direct core.
    """
    direct = direct_view_consumers(graph)
    result: dict[str, list[str]] = {k: list(v) for k, v in direct.items()}
    for node in graph.nodes.values():
        if node.kind != "view":
            continue
        mine = direct.get(node.name)
        if not mine:
            continue
        for anc in node.attrs.get("resolution_chain", []):
            anc = anc.lstrip("+")
            if anc and anc != node.name:
                result.setdefault(anc, []).extend(mine)
    return {name: sorted(set(keys)) for name, keys in result.items()}


def _explores_using_view(graph: IRGraph, view: str) -> list[str]:
    return view_consumer_map(graph).get(view, [])
