"""The Overview report's data: numbers and rows lifted from the tools, nothing analysed here.

Every figure comes from `strata_ir_status`, `strata_usage_summary`, `strata_pdt_costs`,
`strata_schema_drift`, `cleanup_roadmap` or the findings index; this module only formats them
and decides, from `analysis_coverage`, whether a section says "not run" instead of a number.
The sentences themselves are fixed templates in `templates/overview.html`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

from strata_lookml.ir.types import explore_id
from strata_lookml.links import object_path
from strata_lookml.mcp.tools import (
    strata_ir_status,
    strata_pdt_costs,
    strata_schema_drift,
    strata_usage_summary,
)
from strata_lookml.outputs.artifacts import cleanup_roadmap
from strata_lookml.workbench.charts import bar
from strata_lookml.workbench.index import Workbench
from strata_lookml.workbench.render import safe_svg

TOP_EXPLORES = 6
TABLE_ROWS = 10
ACTION_ITEMS = 8
_ACTIONS = {
    "review_for_deprecation": "Review for deprecation",
    "review_unused_pdt_cost": "Review PDT rebuild cost",
    "repair_schema_reference": "Repair the schema reference",
}
_KIND_NOUNS = {"physical_table": "warehouse table", "pdt": "PDT"}
_FINDING_LABELS = {
    "unused-pdt": "unused PDTs",
    "dead-code": "dead code",
    "zombie-pdt": "zombie PDTs",
    "drift": "schema drift",
}


def num(value: float) -> str:
    return f"{int(value):,}"


def plural(n: int, noun: str) -> str:
    return noun if n == 1 else f"{noun}s"


def usd(value: float) -> str:
    return f"${value:,.2f}" if value < 100 else f"${value:,.0f}"


def window_label(period: Mapping[str, Any] | None) -> str | None:
    """The usage window as the facts state it: `30 days`, `14 days`, or None when unrecorded."""
    days = period.get("days") if isinstance(period, Mapping) else None
    if isinstance(days, int) and not isinstance(days, bool) and days > 0:
        return f"{days} days"
    return None


def _bar(value: float, total: float, width: int = 120) -> Any:
    return safe_svg(bar(value, total, width=width))


def _link(graph_has: Any, node_id: str | None) -> str | None:
    return object_path(node_id) if node_id and graph_has(node_id) else None


def overview_context(wb: Workbench) -> dict[str, Any]:
    graph = wb.graph
    l1 = graph.metadata.get("l1", {})
    status = strata_ir_status(graph)
    usage = strata_usage_summary(graph)
    cov = wb.coverage
    window = window_label(usage["period"])
    exists = lambda node_id: graph.get_node(node_id) is not None  # noqa: E731

    counts = status["node_counts"]
    categories = Counter(r["category"] for r in wb.records)
    headline = {
        "repo": wb.repo.name,
        "objects": num(sum(counts.values())),
        "kinds": [(num(n), plural(n, _KIND_NOUNS.get(kind, kind))) for kind, n in counts.items()],
        "edges": num(status["edge_count"]),
        "findings": num(len(wb.records)),
        "categories": [(_FINDING_LABELS.get(c, c), num(n)) for c, n in sorted(categories.items())],
        "commit": wb.source.get("commit") if wb.source else None,
        "branch": wb.source.get("branch") if wb.source else None,
        "window": window,
        "usage_ran": bool(cov.get("usage")),
        "schema_ran": bool(cov.get("schema")),
    }

    # --- usage ---------------------------------------------------------------------------
    rows = sorted(
        l1.get("explore_usage", {}).values(),
        key=lambda r: (-r["query_count"], r["model"], r["explore"]),
    )[:TOP_EXPLORES]
    top_total = sum(r["query_count"] for r in rows)
    top_max = rows[0]["query_count"] if rows else 0
    ir_explores = usage["ir_explore_count"]
    usage_ctx: dict[str, Any] = {
        "ran": bool(cov.get("usage")),
        "window": window,
        "queries": num(usage["total_queries"]),
        "explores": num(ir_explores),
        "active": num(usage["active_explore_count"] or 0),
        "dead": num(usage["dead_explore_count"]),
        "dead_bar": _bar(usage["dead_explore_count"], ir_explores, 160),
        "dead_views": num(usage["dead_view_count"]),
        "dead_views_noun": plural(usage["dead_view_count"], "view"),
        "top_noun": plural(len(rows), "explore"),
        "content_ran": bool(cov.get("content")),
        "top_n": num(len(rows)),
        "top_share": (
            f"{round(100 * top_total / usage['total_queries'])}%"
            if usage["total_queries"] > 0
            else None
        ),
        "top": [
            {
                "label": f"{r['model']}.{r['explore']}",
                "href": _link(exists, explore_id(r["model"], r["explore"])),
                "queries": num(r["query_count"]),
                "bar": _bar(r["query_count"], top_max, 180),
            }
            for r in rows
        ],
    }

    # --- PDT spend -----------------------------------------------------------------------
    ledger = strata_pdt_costs(graph)
    costed = [r for r in ledger if r["status"] != "missing_build_facts"]
    cost_total = sum(r["estimated_cost_usd"] for r in costed)
    wasted = [r for r in costed if r["status"] in ("zombie", "unused")]
    pdt_ctx: dict[str, Any] = {
        "ran": bool(cov.get("usage")),
        "window": window,
        "count": num(len(ledger)),
        "built": bool(costed),
        "missing_facts": num(len(ledger) - len(costed)),
        "total": usd(cost_total),
        "wasted_count": num(len(wasted)),
        "wasted_noun": plural(len(wasted), "PDT"),
        "missing_noun": plural(len(ledger) - len(costed), "PDT"),
        "count_noun": plural(len(ledger), "PDT"),
        "wasted_cost": usd(sum(r["estimated_cost_usd"] for r in wasted)),
        "wasted_bar": _bar(sum(r["estimated_cost_usd"] for r in wasted), cost_total, 160),
        "rows": [
            {
                "name": r["view"],
                "href": _link(exists, f"pdt:{r['view']}"),
                "status": r["status"],
                "builds": num(r["build_count"]),
                "cost": usd(r["estimated_cost_usd"]),
                "bar": _bar(r["estimated_cost_usd"], cost_total, 180),
            }
            for r in sorted(costed, key=lambda r: (-r["estimated_cost_usd"], r["view"]))
        ],
    }

    # --- schema drift --------------------------------------------------------------------
    drift = strata_schema_drift(graph)
    by_table = Counter(r["table"] for r in drift)
    missing_columns = sum(1 for r in drift if r["kind"] == "missing_column")
    missing_tables = sum(1 for r in drift if r["kind"] == "missing_table")
    ranked = sorted(by_table.items(), key=lambda kv: (-kv[1], kv[0]))
    schema_ctx: dict[str, Any] = {
        "ran": bool(cov.get("schema")),
        "columns": num(missing_columns),
        "tables_missing": num(missing_tables),
        "tables": num(len(by_table)),
        "tables_noun": plural(len(by_table), "table"),
        "missing_noun": plural(missing_tables, "table"),
        "any": bool(drift),
        "rows": [
            {
                "name": table,
                "href": _link(exists, f"physical_table:{table}"),
                "refs": num(n),
                "bar": _bar(n, ranked[0][1], 180),
            }
            for table, n in ranked[:TABLE_ROWS]
        ],
        "more": num(max(0, len(ranked) - TABLE_ROWS)),
    }

    # --- next actions --------------------------------------------------------------------
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in cleanup_roadmap(l1):
        evidence = item.get("evidence_ids") or [None]
        groups.setdefault(item["action"], []).append(
            {"target": item["target"], "href": _link(exists, evidence[0])}
        )
    actions_ctx = [
        {
            "label": _ACTIONS.get(action, action),
            "count": num(len(items)),
            "items": items[:ACTION_ITEMS],
            "more": num(max(0, len(items) - ACTION_ITEMS)),
        }
        for action, items in groups.items()
    ]

    return {
        "headline": headline,
        "usage": usage_ctx,
        "pdt": pdt_ctx,
        "schema": schema_ctx,
        "actions": actions_ctx,
    }
