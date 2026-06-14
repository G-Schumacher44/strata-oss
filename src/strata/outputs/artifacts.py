"""Deterministic output artifact generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strata.ir.types import IRGraph
from strata.mcp.tools import strata_impact, strata_usage_summary, strata_validation_scope


def build_artifacts(graph: IRGraph) -> dict[str, Any]:
    l1 = graph.metadata.get("l1", {})
    catalog = [
        {
            "id": node.id,
            "kind": node.kind,
            "name": node.name,
            "source_file": node.source_file,
            "orphan": node.attrs.get("orphan", False),
        }
        for node in sorted(graph.nodes.values(), key=lambda item: item.id)
        if node.kind in {"model", "explore", "view", "field", "pdt", "physical_table"}
    ]
    return {
        "catalog": catalog,
        "dead_code_register": l1.get("dead_code", []),
        "pdt_ledger": l1.get("pdt_ledger", []),
        "schema_drift": l1.get("schema_drift", []),
        "cleanup_roadmap": _cleanup_roadmap(l1),
        "migration_impact": _migration_impact(graph),
        "validation_scope": _validation_scope(graph),
        "usage_summary": strata_usage_summary(graph),
    }


def write_artifacts(graph: IRGraph, output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    artifacts = build_artifacts(graph)
    written: dict[str, str] = {}
    for name, payload in artifacts.items():
        path = out / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written[name] = str(path)
    return written


def _cleanup_roadmap(l1: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in l1.get("dead_code", []):
        items.append(
            {
                "action": "review_for_deprecation",
                "target": record["name"],
                "kind": record["kind"],
                "evidence_ids": record["evidence_ids"],
            }
        )
    for record in l1.get("pdt_ledger", []):
        if record.get("status") == "unused" and record.get("estimated_cost_usd", 0) > 0:
            items.append(
                {
                    "action": "review_unused_pdt_cost",
                    "target": record["view"],
                    "kind": "pdt",
                    "estimated_cost_usd": record["estimated_cost_usd"],
                    "evidence_ids": record["evidence_ids"],
                }
            )
    for record in l1.get("schema_drift", []):
        items.append(
            {
                "action": "repair_schema_reference",
                "target": record["table"] if record["kind"] == "missing_table" else record["field"],
                "kind": record["kind"],
                "evidence_ids": record["evidence_ids"],
            }
        )
    return items


def _migration_impact(graph: IRGraph) -> list[dict[str, Any]]:
    impact: list[dict[str, Any]] = []
    for table in graph.nodes_by_kind("physical_table"):
        impact.append(strata_impact(graph, table.name))
    return impact


def _validation_scope(graph: IRGraph) -> dict[str, Any]:
    changed = graph.metadata.get("validation_scope_inputs", [])
    return (
        strata_validation_scope(graph, changed)
        if changed
        else {"changed": [], "explores": [], "unmatched": []}
    )
