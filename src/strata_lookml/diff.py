"""Findings a ref introduces or fixes: the API behind `strata diff` (and, later, the workbench)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from strata_lookml.gate import finding_records
from strata_lookml.pipeline import build_graph
from strata_lookml.provenance import git_source, materialised, resolve_commit


@dataclass
class DiffResult:
    """`new` = ids only in head, `fixed` = ids only in base; both are full finding records."""

    base: dict[str, Any]
    head: dict[str, Any]
    new: list[dict[str, Any]]
    fixed: list[dict[str, Any]]
    unchanged_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "base": self.base,
            "head": self.head,
            "new": self.new,
            "fixed": self.fixed,
            "unchanged_count": self.unchanged_count,
        }


def classify(
    base: list[dict[str, Any]], head: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """(new, fixed, unchanged_count) by finding id; a duplicated id counts once."""

    def by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {r["id"]: r for r in reversed(records)}  # first record of an id wins

    base_ids, head_ids = by_id(base), by_id(head)
    new = [r for i, r in sorted(head_ids.items()) if i not in base_ids]
    fixed = [r for i, r in sorted(base_ids.items()) if i not in head_ids]
    return new, fixed, len(base_ids.keys() & head_ids.keys())


def diff_findings(
    repo: str | Path,
    base_ref: str,
    head_ref: str | None = None,
    usage_fixture: str | Path | None = None,
    schema_fixture: str | Path | None = None,
) -> DiffResult:
    """Analyse `base_ref` and `head_ref` (default: the working tree) with the same fixtures.

    Refs are exported read-only into a temp dir (see `provenance.materialised`); nothing is
    created in the repo. Raises `InvalidInput` for an unknown ref or a non-git repo.
    """
    root = Path(repo)
    base_commit = resolve_commit(root, base_ref)
    head_commit = resolve_commit(root, head_ref) if head_ref else None

    def analyse(commit: str | None) -> list[dict[str, Any]]:
        if commit is None:
            return finding_records(build_graph(root, usage_fixture, schema_fixture))
        with materialised(root, commit) as snapshot:
            return finding_records(build_graph(snapshot, usage_fixture, schema_fixture))

    base_records = analyse(base_commit)
    head_records = analyse(head_commit)
    new, fixed, unchanged = classify(base_records, head_records)

    head: dict[str, Any] = {"ref": head_ref or "working tree", "commit": head_commit}
    if head_commit is None:
        source = git_source(root)
        head["commit"] = source["commit"] if source else None
        head["dirty"] = bool(source and source["dirty"])
    return DiffResult(
        base={"ref": base_ref, "commit": base_commit},
        head=head,
        new=new,
        fixed=fixed,
        unchanged_count=unchanged,
    )
