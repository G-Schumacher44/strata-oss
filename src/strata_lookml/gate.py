"""The `strata check` gate over a resolved IR graph: integrity always, findings on request."""

from __future__ import annotations

from typing import Any

from strata_lookml.ir.types import IRGraph
from strata_lookml.synthesis.slices import build_explore_slice
from strata_lookml.synthesis.verdicts import deterministic_verdict, validate_verdict

INTEGRITY = "integrity"
# Opt-in finding categories, each with the facts its signal is computed from.
FINDING_CATEGORIES: dict[str, str] = {
    "dead-code": "usage",
    "unused-pdt": "usage",
    "zombie-pdt": "usage",
    "drift": "schema",
}


def _integrity_failures(graph: IRGraph) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for error in graph.metadata.get("resolution_errors", []):
        subject = error.get("name") or "→".join(error.get("chain", []))
        failures.append(
            {
                "category": INTEGRITY,
                "id": f"resolution:{error['kind']}:{error['type']}:{subject}",
                "message": f"{error['kind']} {error['type'].replace('_', ' ')}: {subject}",
            }
        )
    for node in graph.nodes_by_kind("explore"):
        explore_slice = build_explore_slice(graph, node.attrs["model"], node.name)
        verdict = deterministic_verdict(explore_slice)
        for message in validate_verdict(verdict, explore_slice["evidence_ids"]):
            failures.append({"category": INTEGRITY, "id": node.id, "message": message})
    return failures


def _findings(graph: IRGraph) -> dict[str, list[dict[str, str]] | None]:
    """Every finding category's records, or None where its facts were not loaded."""
    l1 = graph.metadata.get("l1", {})
    findings: dict[str, list[dict[str, str]] | None] = dict.fromkeys(FINDING_CATEGORIES)
    if "dead_code" in l1:
        findings["dead-code"] = [
            {"category": "dead-code", "id": r["id"], "message": r["usage_reason"]}
            for r in l1["dead_code"]
        ]
        for status in ("unused", "zombie"):
            findings[f"{status}-pdt"] = [
                {
                    "category": f"{status}-pdt",
                    "id": f"pdt:{r['view']}",
                    "message": f"{status} PDT, {r['build_count']} builds",
                }
                for r in l1["pdt_ledger"]
                if r["status"] == status
            ]
    if "schema_drift" in l1:
        findings["drift"] = [
            {"category": "drift", "id": r["id"], "message": r["reason"]} for r in l1["schema_drift"]
        ]
    return findings


def evaluate_gate(graph: IRGraph, fail_on: set[str]) -> dict[str, Any]:
    """The gate result: `{passed, failures, counts}`.

    Integrity failures always fail; a finding category fails only when named in `fail_on`.
    `counts` has every category; a finding category whose facts were not loaded is null.
    """
    integrity = _integrity_failures(graph)
    findings = _findings(graph)
    failures = integrity + [f for c in sorted(fail_on) for f in findings[c] or []]
    failures.sort(key=lambda f: (f["category"], f["id"], f["message"]))
    counts: dict[str, int | None] = {INTEGRITY: len(integrity)}
    counts.update({c: None if r is None else len(r) for c, r in findings.items()})
    return {"passed": not failures, "failures": failures, "counts": counts}
