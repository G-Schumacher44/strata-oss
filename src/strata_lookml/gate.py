"""The `strata check` gate over a resolved IR graph: integrity always, findings on request."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
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

BASELINE_VERSION = 1


class BaselineError(ValueError):
    """A baseline file that cannot be read or is not a baseline."""


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


def findings_by_category(graph: IRGraph) -> dict[str, list[dict[str, str]] | None]:
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


def baseline_document(graph: IRGraph) -> dict[str, Any]:
    """The baseline for the graph's current findings: sorted, de-duplicated ids per category.

    Only categories whose facts were loaded appear; integrity failures are never baselined.
    """
    findings = findings_by_category(graph)
    return {
        "version": BASELINE_VERSION,
        "findings": {
            c: sorted({f["id"] for f in records})
            for c, records in sorted(findings.items())
            if records is not None
        },
    }


LOOKML_SUFFIXES = {".lkml", ".lookml"}


def _check_baseline_destination(path: Path) -> Path:
    """The resolved destination, or `BaselineError` if writing there could clobber a non-baseline."""
    if path.is_symlink():
        raise BaselineError(f"refusing to write baseline through a symlink: {path}")
    target = path.resolve()
    if target.suffix.lower() in LOOKML_SUFFIXES:
        raise BaselineError(f"refusing to overwrite a LookML file with a baseline: {path}")
    if target.is_dir():
        raise BaselineError(f"baseline destination is a directory: {path}")
    if target.exists():
        try:
            load_baseline(target)
        except BaselineError as exc:
            raise BaselineError(
                f"refusing to overwrite {path}: it is not a previous Strata baseline"
            ) from exc
    return target


def write_baseline(graph: IRGraph, path: Path) -> int:
    """Write the baseline file atomically (indented, trailing newline: diff-friendly).

    Refuses (`BaselineError`, before any write) a symlink, a LookML-suffixed path, or an existing
    file that is not a prior baseline. Returns the id count.
    """
    target = _check_baseline_destination(path)
    document = baseline_document(graph)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".strata-baseline-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return sum(len(ids) for ids in document["findings"].values())


def load_baseline(path: Path) -> dict[str, set[str]]:
    """The baselined ids per finding category; `BaselineError` if the file is not a baseline."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BaselineError(f"cannot read baseline {path}: {exc}") from exc
    found = document.get("findings") if isinstance(document, dict) else None
    if not isinstance(document, dict) or document.get("version") != BASELINE_VERSION:
        raise BaselineError(f"{path} is not a version {BASELINE_VERSION} Strata baseline")
    if not isinstance(found, dict):
        raise BaselineError(f"{path}: 'findings' must be an object of category -> ids")
    baseline: dict[str, set[str]] = {}
    for category, ids in found.items():
        if category not in FINDING_CATEGORIES:
            raise BaselineError(f"{path}: unknown category {category!r}")
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise BaselineError(f"{path}: {category!r} must be a list of id strings")
        baseline[category] = set(ids)
    return baseline


def evaluate_gate(
    graph: IRGraph, fail_on: set[str], baseline: dict[str, set[str]] | None = None
) -> dict[str, Any]:
    """The gate result: `{passed, failures, counts}`.

    Integrity failures always fail; a finding category fails only when named in `fail_on`.
    `counts` has every category; a finding category whose facts were not loaded is null.

    With a `baseline`, known finding ids are subtracted before `fail_on` applies, so only new
    findings fail; integrity is never subtracted. The result then also carries `baselined` (the
    findings it suppressed) and `stale_baseline_ids` (baselined ids no longer found, in
    categories whose facts were loaded; a warning, never a failure).
    """
    integrity = _integrity_failures(graph)
    findings = findings_by_category(graph)
    known = baseline or {}
    baselined = 0
    failures = list(integrity)
    for category in sorted(fail_on):
        for finding in findings[category] or []:
            if finding["id"] in known.get(category, ()):
                baselined += 1
            else:
                failures.append(finding)
    failures.sort(key=lambda f: (f["category"], f["id"], f["message"]))
    counts: dict[str, int | None] = {INTEGRITY: len(integrity)}
    counts.update({c: None if r is None else len(r) for c, r in findings.items()})
    result: dict[str, Any] = {"passed": not failures, "failures": failures, "counts": counts}
    if baseline is not None:
        result["baselined"] = baselined
        result["stale_baseline_ids"] = sorted(
            {
                i
                for c, ids in known.items()
                if findings[c] is not None
                for i in ids - {f["id"] for f in findings[c] or []}
            }
        )
    return result
