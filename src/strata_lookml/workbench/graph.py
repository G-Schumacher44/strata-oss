"""The workbench graph: the Cytoscape graph data, its palette, and a focus neighbourhood.

`build_graph_data` is the one graph-data builder (the legacy dashboard imports it from here
until S10 deletes that renderer). `neighbourhood` cuts the focus view out of it (M4): one hop
both ways by default, two hops per direction on request, siblings opt-in, capped at
`NODE_CAP` nodes with the full count reported. Plain Python: no HTTP, no templates.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from strata_lookml.ir.types import IRGraph, explore_key
from strata_lookml.l1.enrich import analysis_coverage, view_consumer_map
from strata_lookml.links import object_path

# The one source for graph status colors: build_graph_data stamps these onto nodes/edges
# and every page (the workbench layout, the legacy dashboard) emits the same dict as CSS
# custom properties (--n-<key>), which legends, status badges and theme tokens read. A node can never disagree with the legend that
# explains it, because both come from here.
NODE_PALETTE = {
    "explore_active": "#3fbf8f",
    "explore_dead": "#f06b5d",
    "explore_unknown": "#8f9aab",  # usage facts not loaded: activity is unknown, not active
    "view_active": "#6aa5e0",
    "view_orphan": "#7c8696",
    "zombie": "#a98bf5",
    "pdt_unused": "#eaa53f",
    "pdt_used": "#3fbf8f",
    "pdt_unknown": "#8f9aab",
    "physical_table": "#6f7f94",
}
EDGE_PALETTE = {
    "explore→base_view": "#9fb0c6",
    "explore→joined_view": "#6d7c91",
    "view→physical_table": "#55637a",
    "view→pdt": "#eaa53f",
}


def node_var(key: str) -> str:
    """The custom property name for a NODE_PALETTE key: `explore_dead` -> `n-explore-dead`."""
    return "n-" + key.replace("_", "-")


def edge_var(relation: str) -> str:
    """The custom property name for an EDGE_PALETTE relation, by its target kind:
    `explore→joined_view` -> `e-joined-view`."""
    return "e-" + relation.split("→")[1].replace("_", "-")


def palette_css() -> str:
    """Both palettes as CSS custom properties for a page's :root block: --n-<status>
    for nodes, --e-<target kind> for edges (e.g. explore→joined_view -> --e-joined-view)."""
    nodes = [f"--{node_var(key)}: {hex_};" for key, hex_ in NODE_PALETTE.items()]
    edges = [f"--{edge_var(relation)}: {hex_};" for relation, hex_ in EDGE_PALETTE.items()]
    return " ".join(nodes + edges)


def build_graph_data(graph: IRGraph) -> dict[str, Any]:
    """Every explore, view, PDT and warehouse table as Cytoscape elements, coloured from
    NODE_PALETTE/EDGE_PALETTE. The workbench graph cuts a focus neighbourhood out of this; the
    legacy dashboard renders all of it."""
    l1 = graph.metadata.get("l1", {})
    # G15 invariant: the register names an explore by its model-qualified key
    # (`explore_key`, always dotted) and a view by its bare name (never dotted in LookML), so
    # the two namespaces cannot collide. Kept as two sets so no lookup can cross them.
    dead_code = l1.get("dead_code", [])
    dead_explore_keys = {r["name"] for r in dead_code if r.get("kind") == "explore"}
    dead_view_names = {r["name"] for r in dead_code if r.get("kind") == "view"}
    _eu = l1.get("explore_usage", {})
    usage_map = (
        {k: v["query_count"] for k, v in _eu.items()}
        if isinstance(_eu, dict)
        else {
            explore_key(r["model"], r["explore"]): r["query_count"]
            for r in _eu
            if isinstance(r, dict)
        }
    )
    pdt_records = {r["view"]: r for r in l1.get("pdt_ledger", [])}
    # Dead status needs usage evidence; with none loaded an explore is "unknown", never green.
    usage_loaded = analysis_coverage(graph)["usage"]

    # One edge pass builds every cross-kind lookup the node-detail panel needs — computed
    # once here so the panel never re-derives a fact JS-side that L1 already established
    # (the model-qualified-dead-explore bug from PR #21 was exactly that kind of drift).
    explore_views: dict[str, list[str]] = {}
    view_pdt: dict[str, str] = {}
    table_views: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.relation in {"explore→base_view", "explore→joined_view"} and edge.target.startswith(
            "view:"
        ):
            explore_node = graph.nodes.get(edge.source)
            view_name = edge.target.removeprefix("view:")
            if explore_node and explore_node.kind == "explore":
                explore_views.setdefault(explore_node.id, []).append(view_name)
        elif edge.relation == "view→pdt" and edge.target.startswith("pdt:"):
            view_pdt[edge.source.removeprefix("view:")] = edge.target.removeprefix("pdt:")
        elif edge.relation == "view→physical_table" and edge.target.startswith("physical_table:"):
            table_views.setdefault(edge.target.removeprefix("physical_table:"), []).append(
                edge.source.removeprefix("view:")
            )
        elif edge.relation == "pdt→upstream" and edge.target.startswith("physical_table:"):
            # Derived-table SQL references count too: the resolver records them as
            # pdt→upstream, and strata_impact() maps the PDT back to its view
            # (mcp/tools.py) — the panel mirrors that mapping or it undercounts exactly
            # the references a deletion would break (Codex r5, PR #25).
            pdt_node = graph.nodes.get(edge.source)
            if pdt_node is not None:
                table_views.setdefault(edge.target.removeprefix("physical_table:"), []).append(
                    pdt_node.name
                )
    # Consumers come from L1's ancestry-aware single source — the dashboard must never
    # re-derive them (PR #25 Codex round 2: a local propagation here could disagree with
    # the register/ledger, which use the same map via _explores_using_view).
    view_explores = view_consumer_map(graph)
    table_views = {name: sorted(set(views)) for name, views in table_views.items()}

    def consumers(keys: list[str]) -> list[dict[str, Any]]:
        return [{"key": k, "dead": k in dead_explore_keys} for k in keys]

    # An explore displays as its bare name unless another model has an explore of that name.
    explore_names = Counter(node.name for node in graph.nodes_by_kind("explore"))
    shared_explore_names = {name for name, count in explore_names.items() if count > 1}

    nodes = []
    for node in graph.nodes.values():
        if node.kind not in {"explore", "view", "physical_table", "pdt"}:
            continue
        model = node.attrs.get("model", "")
        # Dead-code register names EXPLORES model-qualified ("em_legacy_v2.dead_finance_v2")
        # but views bare — a bare-name lookup silently missed every dead explore, so they
        # rendered green/KEEP in the graph (caught regenerating the README screenshots on
        # PR #21: dead_finance_v2 showed QUERY COUNT 0 with a KEEP badge).
        is_dead = (
            (explore_key(model, node.name) in dead_explore_keys)
            if node.kind == "explore"
            else (node.name in dead_view_names)
        )
        qcount = usage_map.get(explore_key(model, node.name), 0) if node.kind == "explore" else 0
        is_orphan_struct = bool(node.attrs.get("orphan", False))
        orphan = is_orphan_struct or is_dead

        extra: dict[str, Any] = {}
        if node.kind == "explore":
            views_for_explore = explore_views.get(node.id, [])
            extra["pdt_dependencies"] = sorted(
                {view_pdt[v] for v in views_for_explore if v in view_pdt}
            )
            extra["status"] = "dead" if is_dead else "active" if usage_loaded else "unknown"
            color = NODE_PALETTE[
                "explore_dead"
                if is_dead
                else "explore_active"
                if usage_loaded
                else "explore_unknown"
            ]
            shape = "ellipse"
            # Demand reads as size, capped so a heavy explore can't crowd its rank.
            size = max(14, min(28, 14 + qcount // 50))
        elif node.kind == "pdt":
            record = pdt_records.get(node.name)
            status = record["status"] if record else "missing_build_facts"
            extra.update(
                status=status,
                estimated_cost_usd=record["estimated_cost_usd"] if record else 0.0,
                build_count=record["build_count"] if record else 0,
                bytes_processed=record["bytes_processed"] if record else 0,
                used_by_explores=consumers(record["used_by_explores"] if record else []),
            )
            # Zombie (real infra, dead demand) is purple; unused is orange; in-use is
            # green — the three-way vocabulary the legend teaches (see #2 in the slice).
            color = NODE_PALETTE[
                "zombie"
                if status == "zombie"
                else "pdt_unused"
                if status == "unused"
                else "pdt_used"
                if status == "used"
                else "pdt_unknown"  # missing_build_facts — no cost data to render a verdict from
            ]
            shape = "diamond"
            size = 22
        elif node.kind == "view":
            referencing = view_explores.get(node.name, [])
            # Zombie view: structurally referenced (unlike a true orphan) but every
            # referencing explore is itself dead — alive wiring, dead demand.
            is_zombie_view = (
                not is_orphan_struct
                and bool(referencing)
                and all(k in dead_explore_keys for k in referencing)
            )
            view_status = (
                "orphaned" if is_orphan_struct else "zombie_view" if is_zombie_view else "active"
            )
            extra.update(status=view_status, referencing_explores=consumers(referencing))
            color = NODE_PALETTE[
                "view_orphan" if is_orphan_struct else "zombie" if is_zombie_view else "view_active"
            ]
            shape = "round-rectangle"
            size = 16
        else:  # physical_table
            extra["referencing_views"] = table_views.get(node.name, [])
            color = NODE_PALETTE["physical_table"]
            shape = "barrel"
            size = 16

        # One flag the graph's "Needs attention" filter reads, so the filter can't drift from
        # the statuses above: dead/orphaned anything, zombie views, zombie or unused PDTs.
        attention = orphan or extra.get("status") in {"zombie", "unused", "zombie_view"}

        nodes.append(
            {
                "data": {
                    "id": node.id,
                    # `label` stays the bare name: the JS builds `model.label` fact keys from it.
                    "label": node.name,
                    "display_label": explore_key(model, node.name)
                    if node.kind == "explore" and node.name in shared_explore_names
                    else node.name,
                    "kind": node.kind,
                    "source_file": node.source_file,
                    "dead": is_dead,
                    "orphan": orphan,
                    "attention": attention,
                    "query_count": qcount,
                    "model": model,
                    "color": color,
                    "size": size,
                    "shape": shape,
                    **extra,
                }
            }
        )

    edges = []
    seen = set()
    for edge in graph.edges:
        if edge.relation not in {
            "explore→base_view",
            "explore→joined_view",
            "view→physical_table",
            "view→pdt",
        }:
            continue
        edge_key = (edge.source, edge.target, edge.relation)
        if edge_key in seen:
            continue
        seen.add(edge_key)
        if edge.source not in graph.nodes or edge.target not in graph.nodes:
            continue
        src = graph.nodes[edge.source]
        tgt = graph.nodes[edge.target]
        if src.kind not in {"explore", "view", "pdt"} or tgt.kind not in {
            "view",
            "physical_table",
            "pdt",
        }:
            continue

        edges.append(
            {
                "data": {
                    "id": f"{edge.source}__{edge.target}",
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "color": EDGE_PALETTE[edge.relation],
                }
            }
        )

    return {"nodes": nodes, "edges": edges}


# --- focus neighbourhood (M4) -----------------------------------------------------------------

NODE_CAP = 40
MAX_HOPS = 2

# Legend wording per palette entry, in legend order. Every NODE_PALETTE / EDGE_PALETTE key
# has one (tests/test_workbench_graph.py), so a new status cannot ship without a legend line.
NODE_LEGEND = {
    "explore_active": "active explore",
    "explore_dead": "dead explore",
    "explore_unknown": "explore, usage not loaded",
    "view_active": "view",
    "view_orphan": "orphan view",
    "zombie": "zombie view / PDT",
    "pdt_used": "PDT in use",
    "pdt_unused": "unused PDT",
    "pdt_unknown": "PDT, no build facts",
    "physical_table": "warehouse table",
}
EDGE_LEGEND = {
    "explore→base_view": "base view",
    "explore→joined_view": "joined view",
    "view→physical_table": "sql_table_name",
    "view→pdt": "derived table",
}

# Ring names, in the order the cap keeps them: the focus, then one hop each way, then the
# second hop each way, then siblings. "upstream" is what the focus reads (its out-edges, the
# detail pages' "Upstream · reads from"); "downstream" is what reads it.
RINGS = ("focus", "upstream 1", "downstream 1", "upstream 2", "downstream 2", "siblings")


_STATUS_WORDS = {
    "zombie_view": "zombie view",
    "orphaned": "orphan view",
    "missing_build_facts": "no build facts",
}


def caption(data: dict[str, Any]) -> str:
    """A node's one-line status under its name, from the fields `build_graph_data` set."""
    kind, status = data["kind"], data.get("status")
    if kind == "explore":
        if status == "unknown":
            return "usage not loaded"
        count = data.get("query_count", 0)
        return (
            "dead · 0 queries"
            if status == "dead"
            else f"{count:,} {'query' if count == 1 else 'queries'}"
        )
    if kind == "physical_table":
        return "warehouse table"
    word = _STATUS_WORDS.get(str(status), str(status))
    if kind == "pdt" and data.get("estimated_cost_usd"):
        return f"{word} · ${data['estimated_cost_usd']:,.0f} rebuilds"
    return word


def neighbourhood(
    data: dict[str, Any],
    focus: str,
    *,
    up: int = 1,
    down: int = 1,
    siblings: bool = False,
    cap: int = NODE_CAP,
) -> dict[str, Any] | None:
    """The focus neighbourhood of `build_graph_data` output, or None when `focus` is not a node.

    Walks `up` hops along out-edges and `down` hops along in-edges (each 0..MAX_HOPS); with
    `siblings`, adds the other children of the focus's direct parents (the other views an
    explore joins, the other tables a view's parent explores reach through it). Nodes keep
    the ring they were first reached in, in `RINGS` order, sorted by id within a ring; the
    first `cap` are kept and `total` is the uncapped count. Edges are every graph edge between
    two kept nodes. Each node gains `ring`, `caption`, `focus` and `path` (its page or None).
    """
    nodes = {n["data"]["id"]: n["data"] for n in data["nodes"]}
    if focus not in nodes:
        return None
    edges = [e["data"] for e in data["edges"]]
    out_edges: dict[str, set[str]] = {}
    in_edges: dict[str, set[str]] = {}
    for e in edges:
        out_edges.setdefault(e["source"], set()).add(e["target"])
        in_edges.setdefault(e["target"], set()).add(e["source"])

    ring: dict[str, str] = {focus: "focus"}
    order: list[str] = [focus]

    def reach(frontier: set[str], step: dict[str, set[str]]) -> set[str]:
        return {n for f in frontier for n in step.get(f, ())}

    up_frontier, down_frontier = {focus}, {focus}
    for hop in range(1, MAX_HOPS + 1):
        found: list[tuple[str, set[str]]] = []
        if hop <= up:
            up_frontier = reach(up_frontier, out_edges) - ring.keys()
            found.append((f"upstream {hop}", up_frontier))
        if hop <= down:
            down_frontier = reach(down_frontier, in_edges) - ring.keys()
            found.append((f"downstream {hop}", down_frontier))
        for name, ids in found:
            for node_id in sorted(ids - ring.keys()):
                ring[node_id] = name
                order.append(node_id)
    if siblings:
        for node_id in sorted(reach(in_edges.get(focus, set()), out_edges) - ring.keys()):
            ring[node_id] = "siblings"
            order.append(node_id)

    kept = order[: max(1, cap)]
    keep = set(kept)
    return {
        "focus": focus,
        "up": up,
        "down": down,
        "siblings": siblings,
        "total": len(order),
        "shown": len(kept),
        "nodes": [
            {
                "data": {
                    **nodes[node_id],
                    "ring": ring[node_id],
                    "caption": caption(nodes[node_id]),
                    "focus": node_id == focus,
                    "path": object_path(node_id),
                }
            }
            for node_id in kept
        ],
        "edges": [{"data": e} for e in edges if e["source"] in keep and e["target"] in keep],
    }
