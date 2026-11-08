"""The `strata check` gate over a resolved IR graph: integrity always, findings on request."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from strata_lookml.ir.types import IRGraph, explore_key
from strata_lookml.safe_paths import check_write_destination
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


def _rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [{k: r[k] for k in ("category", "id", "message")} for r in records]


def _integrity_failures(graph: IRGraph) -> list[dict[str, str]]:
    return _rows(_integrity_records(graph))


def _short_table(table: str, parts: int) -> str:
    """The trailing `parts` dot-separated segments of a table name (drops project/dataset)."""
    return ".".join(table.split(".")[-parts:])


def _record(
    graph: IRGraph,
    category: str,
    finding_id: str,
    message: str,
    label: str,
    subject_id: str,
    source_file: str | None,
    evidence_ids: list[str],
    cost_usd: float | None = None,
    line_from: str | None = None,
) -> dict[str, Any]:
    subject = graph.get_node(subject_id)
    cited = graph.get_node(line_from) if line_from else subject
    record: dict[str, Any] = {
        "category": category,
        "id": finding_id,
        "message": message,
        "label": label,
        "subject_id": subject_id,
        "source_file": source_file or (subject.source_file if subject else None),
        "source_line": cited.attrs.get("source_line") if cited else None,
        "evidence_ids": list(evidence_ids),
    }
    if cost_usd is not None:
        record["cost_usd"] = cost_usd
    return record


def _integrity_records(graph: IRGraph) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for error in graph.metadata.get("resolution_errors", []):
        subject = error.get("name") or "\u2192".join(error.get("chain", []))
        reason = error["type"].replace("_", " ")
        # A resolution error names the missing/cyclic object, not where it was declared, so it
        # has no subject node, file or line: None rather than a guess.
        records.append(
            {
                "category": INTEGRITY,
                "id": f"resolution:{error['kind']}:{error['type']}:{subject}",
                "message": f"{error['kind']} {reason}: {subject}",
                "label": f"{subject}: {reason}",
                "subject_id": None,
                "source_file": error.get("source_file"),
                "source_line": None,
                "evidence_ids": [],
            }
        )
    for node in graph.nodes_by_kind("explore"):
        explore_slice = build_explore_slice(graph, node.attrs["model"], node.name)
        verdict = deterministic_verdict(explore_slice)
        for message in validate_verdict(verdict, explore_slice["evidence_ids"]):
            records.append(
                _record(
                    graph,
                    INTEGRITY,
                    node.id,
                    message,
                    f"{node.name}: {message}",
                    node.id,
                    None,
                    explore_slice["evidence_ids"],
                )
            )
    return records


def finding_records(graph: IRGraph) -> list[dict[str, Any]]:
    """Every finding as a full record, integrity failures first, then the opt-in categories.

    The one source the gate and baseline project from.

    `{category, id, message, label, subject_id, source_file, source_line, evidence_ids,
    cost_usd?}`: `subject_id` is the IR node the finding is about (resolves via `graph.get_node`),
    `label` the short per-category display string (the full `id` stays the key), `cost_usd` only
    on PDT findings. Integrity records (ids as the gate reports them) have a `subject_id` only
    for explore failures; resolution errors carry no node, file or line, so those are None.
    Categories whose facts were not loaded contribute no records. Duplicate ids
    yield one record each (two fields of one name can miss the same column); the baseline
    de-duplicates, ids are never changed.
    """
    return _integrity_records(graph) + _opt_in_records(graph)


def _opt_in_records(graph: IRGraph) -> list[dict[str, Any]]:
    l1 = graph.metadata.get("l1", {})
    explore_ids = {
        explore_key(n.attrs.get("model", ""), n.name): n.id for n in graph.nodes_by_kind("explore")
    }
    records: list[dict[str, Any]] = []
    for r in l1.get("dead_code", []):
        subject_id = (
            explore_ids.get(r["name"], "") if r["kind"] == "explore" else f"view:{r['name']}"
        )
        records.append(
            _record(
                graph,
                "dead-code",
                r["id"],
                r["usage_reason"],
                r["name"],
                subject_id,
                r["source_file"],
                r["evidence_ids"],
            )
        )
    for status in ("unused", "zombie"):
        for r in l1.get("pdt_ledger", []):
            if r["status"] != status:
                continue
            records.append(
                _record(
                    graph,
                    f"{status}-pdt",
                    f"pdt:{r['view']}",
                    f"{status} PDT, {r['build_count']} builds",
                    r["view"],
                    f"pdt:{r['view']}",
                    r["source_file"],
                    r["evidence_ids"],
                    cost_usd=r["estimated_cost_usd"],
                )
            )
    for r in l1.get("schema_drift", []):
        if r["kind"] == "missing_column":
            label = f"{r['field']} \u2190 {_short_table(r['table'], 1)}.{r['column']}"
            subject_id = r["evidence_ids"][0]
            line_from = None
        else:
            label = _short_table(r["table"], 2)
            subject_id = f"physical_table:{r['table']}"
            # A table node has no line of its own: cite the first view that reads it.
            line_from = next(
                (
                    e.source
                    for e in graph.edges
                    if e.relation == "view\u2192physical_table" and e.target == subject_id
                ),
                None,
            )
        records.append(
            _record(
                graph,
                "drift",
                r["id"],
                r["reason"],
                label,
                subject_id,
                r["source_file"],
                r["evidence_ids"],
                line_from=line_from,
            )
        )
    return records


def findings_by_category(graph: IRGraph) -> dict[str, list[dict[str, str]] | None]:
    """Every finding category's `{category, id, message}` rows, or None where facts were not loaded."""
    l1 = graph.metadata.get("l1", {})
    loaded = {
        "dead-code": "dead_code" in l1,
        "unused-pdt": "dead_code" in l1,
        "zombie-pdt": "dead_code" in l1,
        "drift": "schema_drift" in l1,
    }
    findings: dict[str, list[dict[str, str]] | None] = {
        c: [] if loaded[c] else None for c in FINDING_CATEGORIES
    }
    for record in _opt_in_records(graph):
        rows = findings[record["category"]]
        assert rows is not None
        rows.extend(_rows([record]))
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


def _is_baseline(path: Path) -> bool:
    try:
        load_baseline(path)
    except BaselineError:
        return False
    return True


def write_baseline(graph: IRGraph, path: Path) -> int:
    """Write the baseline file atomically (indented, trailing newline: diff-friendly).

    Refuses (`InvalidInput`, before any write) a symlink, a LookML-suffixed path, a directory,
    or an existing file that is not a prior baseline (`safe_paths.check_write_destination`).
    Returns the id count.
    """
    target = check_write_destination(path, what="baseline", is_ours=_is_baseline)
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
