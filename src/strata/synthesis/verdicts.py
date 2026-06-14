"""Deterministic verdict helpers and evidence validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SynthesisVerdict:
    slice_id: str
    verdict: str
    rationale: str
    evidence_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def deterministic_verdict(explore_slice: dict[str, Any]) -> SynthesisVerdict:
    dead = explore_slice.get("dead_code_evidence", [])
    usage = explore_slice.get("usage") or {}
    if dead and usage.get("query_count", 0) == 0:
        verdict = "deprecate"
        rationale = "zero usage plus structural/static dead-code evidence"
    elif usage.get("query_count", 0) > 0:
        verdict = "keep"
        rationale = "explore has recent usage evidence"
    else:
        verdict = "review"
        rationale = "insufficient usage evidence for an automatic keep/deprecate verdict"
    return SynthesisVerdict(
        slice_id=explore_slice["id"],
        verdict=verdict,
        rationale=rationale,
        evidence_ids=list(explore_slice.get("evidence_ids", [])),
    )


def validate_verdict(
    verdict: SynthesisVerdict | dict[str, Any], evidence_ids: list[str]
) -> list[str]:
    data = verdict.to_dict() if isinstance(verdict, SynthesisVerdict) else verdict
    errors: list[str] = []
    if data.get("verdict") not in {"keep", "hide", "deprecate", "kill", "review"}:
        errors.append("verdict must be one of keep/hide/deprecate/kill/review")
    if not data.get("rationale"):
        errors.append("verdict rationale is required")
    provided = set(data.get("evidence_ids") or [])
    allowed = set(evidence_ids)
    missing = provided - allowed
    if missing:
        errors.append(f"verdict references unknown evidence ids: {sorted(missing)}")
    if data.get("verdict") in {"hide", "deprecate", "kill"}:
        if not provided:
            errors.append("actionable verdicts require evidence")
        uncited = allowed - provided
        if uncited:
            errors.append(f"actionable verdict has uncited available evidence: {sorted(uncited)}")
    return errors
