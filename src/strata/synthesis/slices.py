"""Bounded synthesis slices over IR + L1 evidence."""

from __future__ import annotations

from typing import Any

from strata.ir.types import IRGraph
from strata.mcp.tools import strata_explore_deps


def build_explore_slice(graph: IRGraph, model: str, explore: str) -> dict[str, Any]:
    """Create a compact, evidence-only slice for one explore."""

    key = f"{model}.{explore}"
    deps = strata_explore_deps(graph, explore, model)
    l1 = graph.metadata.get("l1", {})
    dead_code = [
        item for item in l1.get("dead_code", []) if item.get("name") in {key, deps["base_view"]}
    ]
    pdt_ledger = [
        item for item in l1.get("pdt_ledger", []) if key in item.get("used_by_explores", [])
    ]
    return {
        "id": f"slice:explore:{key}",
        "model": model,
        "explore": explore,
        "dependencies": deps,
        "usage": l1.get("explore_usage", {}).get(key),
        "content_references": [
            item
            for item in l1.get("content_references", [])
            if f"{item['model']}.{item['explore']}" == key
        ],
        "dead_code_evidence": dead_code,
        "pdt_evidence": pdt_ledger,
        "evidence_ids": _evidence_ids(dead_code, pdt_ledger),
    }


def _evidence_ids(*groups: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for group in groups:
        for item in group:
            ids.extend(item.get("evidence_ids", []))
    return sorted(set(ids))
