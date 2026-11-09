"""The PR-comment text for a finding or an object: a pure function, no HTTP or rendering.

The page embeds the result in a read-only textarea and a copy button puts it on the clipboard,
so what an engineer pastes is exactly what is tested. With a workbench base each item links to
its page (`links.link`); without one the links are left out (a guessed port would be wrong).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from strata_lookml.links import finding_path, link, object_path

CATEGORY_LABELS = {
    "dead-code": "dead code",
    "zombie-pdt": "zombie PDT",
    "unused-pdt": "unused PDT",
    "drift": "schema drift",
    "integrity": "integrity",
}
ACTION_LABELS = {
    "review_for_deprecation": "Review for deprecation",
    "review_unused_pdt_cost": "Review PDT rebuild cost",
    "repair_schema_reference": "Repair schema reference",
}
# The cleanup action a finding category maps to (the roadmap's own action names).
CATEGORY_ACTIONS = {
    "dead-code": "review_for_deprecation",
    "zombie-pdt": "review_unused_pdt_cost",
    "unused-pdt": "review_unused_pdt_cost",
    "drift": "repair_schema_reference",
}


def _location(record: Mapping[str, Any]) -> str | None:
    file = record.get("source_file")
    if not file:
        return None
    line = record.get("source_line")
    return f"{file}:{line}" if line else str(file)


def usd(amount: float) -> str:
    return f"${amount:,.0f}" if amount >= 100 else f"${amount:,.2f}"


def pr_comment(
    records: Sequence[Mapping[str, Any]],
    obj: Mapping[str, Any],
    workbench_base: str | None = None,
    verdict: tuple[str, str] | None = None,
) -> str:
    """Markdown for a PR review about `records` (finding records) on `obj` (a `strata_object`).

    With no records the comment is about the object itself and carries its `verdict`
    (label, rationale) when given. `workbench_base` None means no links at all.
    """
    subject = f"{obj['kind']} `{obj['name']}`"
    lines: list[str] = []
    if records:
        noun = "finding" if len(records) == 1 else "findings"
        # A finding page is about the finding itself: no object to name.
        on = "" if obj["kind"] == "finding" else f" on {subject}"
        lines.append(f"**Strata** found {len(records)} LookML {noun}{on}:")
        lines.append("")
        for record in records:
            label = CATEGORY_LABELS.get(record["category"], record["category"])
            lines.append(f"- **{label}** `{record['id']}`")
            where = _location(record)
            lines.append(
                f"  - `{where}` — {record['message']}" if where else f"  - {record['message']}"
            )
            if record.get("cost_usd") is not None:
                lines.append(f"  - Rebuild cost: {usd(record['cost_usd'])}")
            action = CATEGORY_ACTIONS.get(record["category"])
            if action:
                lines.append(f"  - Suggested: {ACTION_LABELS[action]}")
            if record.get("evidence_ids"):
                lines.append("  - Evidence: " + ", ".join(f"`{e}`" for e in record["evidence_ids"]))
            url = link(workbench_base, finding_path(record["id"]))
            if url:
                lines.append(f"  - Workbench: {url}")
        return "\n".join(lines)
    lines.append(f"**Strata** on {subject}:")
    lines.append("")
    where = _location(
        {"source_file": obj.get("source_file"), "source_line": obj.get("source_line")}
    )
    if where:
        lines.append(f"- `{where}`")
    if verdict:
        lines.append(f"- {verdict[0]}: {verdict[1]}")
    else:
        lines.append("- No findings on this object.")
    url = link(workbench_base, object_path(obj["id"]))
    if url:
        lines.append(f"- Workbench: {url}")
    return "\n".join(lines)
