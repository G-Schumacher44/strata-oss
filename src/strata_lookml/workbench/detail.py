"""View models for the detail pages (explore, view, pdt, table, field, finding).

Plain data in, plain data out: `App` hands the result to `detail.html` / `finding.html`, which
escape every value. Nothing here builds markup. Links come from `links.py`; the verdict for an
explore is `synthesis.verdicts.deterministic_verdict`, for any other object the cleanup-roadmap
action (`outputs.artifacts.cleanup_roadmap`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from strata_lookml.identifiers import explores_by_key
from strata_lookml.ir.types import explore_id
from strata_lookml.links import finding_path, object_path
from strata_lookml.synthesis.slices import build_explore_slice
from strata_lookml.synthesis.verdicts import deterministic_verdict
from strata_lookml.triage import TriageRow
from strata_lookml.workbench.index import Workbench
from strata_lookml.workbench.pr_text import ACTION_LABELS, CATEGORY_ACTIONS, CATEGORY_LABELS, usd

SHOWN = 200  # rows per lineage group; the rest are counted, not rendered

KIND_LABELS = {
    "explore": "Explore",
    "view": "View",
    "pdt": "PDT",
    "table": "Warehouse table",
    "field": "Field",
}
RELATION_LABELS = {
    "base_view": "base view",
    "joined_view": "joined view",
    "view": "view",
    "physical_table": "sql_table_name",
    "pdt": "derived table",
    "extends": "extends",
    "explore": "explore",
    "views": "view",
    "explores": "explore",
    "fields": "field",
}
# Relation group -> IR node id prefix, for the groups whose members are plain names.
_PREFIX = {
    "base_view": "view:",
    "joined_view": "view:",
    "view": "view:",
    "extends": "view:",
    "views": "view:",
    "physical_table": "physical_table:",
    "pdt": "pdt:",
    "fields": "field:",
}
_MARKS = {"dead-code": "dead", "zombie-pdt": "zombie"}
VERDICT_CLASS = {
    "keep": "ok",
    "review": "muted",
    "hide": "dead",
    "deprecate": "dead",
    "kill": "dead",
    "review_for_deprecation": "dead",
    "review_unused_pdt_cost": "zombie",
    "repair_schema_reference": "drift",
}


class Detail:
    """Builds detail view models over one `Workbench`; the roadmap is indexed once."""

    def __init__(self, wb: Workbench, roadmap: Sequence[Mapping[str, Any]]) -> None:
        self.wb = wb
        self._roadmap: dict[str, list[Mapping[str, Any]]] = {}
        for item in roadmap:
            # An item's first evidence id is its own subject node (`explore:`, `view:`, `pdt:`,
            # `field:`, `physical_table:`): match by node identity, never by the shared name.
            if item["evidence_ids"]:
                self._roadmap.setdefault(item["evidence_ids"][0], []).append(item)

    # --- shared pieces -----------------------------------------------------------------

    def mark(self, node_id: str) -> str | None:
        """`dead` / `zombie` when a finding of that category sits on the node.

        A PDT's view carries its PDT's mark (the zombie finding sits on `pdt:<name>`); zombie
        wins over dead because it is the more specific finding.
        """
        candidates = [node_id]
        if node_id.startswith("view:"):
            candidates.append("pdt:" + node_id.removeprefix("view:"))
        marks = {
            _MARKS[record["category"]]
            for candidate in candidates
            for finding_id in self.wb.findings_by_node.get(candidate, ())
            for record in self.wb.findings_by_id.get(finding_id, ())
            if record["subject_id"] == candidate and record["category"] in _MARKS
        }
        return "zombie" if "zombie" in marks else ("dead" if marks else None)

    def ref(self, node_id: str, text: str | None = None) -> dict[str, Any]:
        """A node as a link when it has a page and exists in the graph, else plain text."""
        node = self.wb.graph.get_node(node_id)
        href = object_path(node_id) if node is not None else None
        return {"text": text or node_id, "href": href, "mark": self.mark(node_id), "kind": None}

    def evidence(self, ids: Sequence[str]) -> list[dict[str, Any]]:
        """Evidence ids as chips: an object link, a finding link, or plain text."""
        chips = []
        for evidence_id in ids:
            href = (
                finding_path(evidence_id)
                if evidence_id in self.wb.findings_by_id
                else (object_path(evidence_id) if self.wb.graph.get_node(evidence_id) else None)
            )
            chips.append({"text": evidence_id, "href": href})
        return chips

    def card(self, record: Mapping[str, Any], rows: Mapping[str, TriageRow]) -> dict[str, Any]:
        """A finding as the pages show it; its status is `triage_rows`' (the one source)."""
        row = rows.get(record["id"])
        return {
            "status": row.status if row else "new",
            "acked_at": row.acked_at if row else None,
            "note": row.note if row else None,
            "id": record["id"],
            "href": finding_path(record["id"]),
            "category": record["category"],
            "category_label": CATEGORY_LABELS.get(record["category"], record["category"]),
            "message": record["message"],
        }

    def group(self, key: str, members: Sequence[Any]) -> dict[str, Any]:
        items = []
        for member in list(members)[:SHOWN]:
            items.append(self._member(key, member))
        return {
            "label": RELATION_LABELS.get(key, key),
            "items": items,
            "more": max(0, len(members) - SHOWN),
        }

    def _member(self, key: str, member: str) -> dict[str, Any]:
        if key in _PREFIX:
            return self.ref(_PREFIX[key] + member, member)
        if key in ("explore", "explores"):
            found = explores_by_key(self.wb.graph, member)
            if len(found) == 1:  # more than one: the key's own page lists the candidates
                node_id = explore_id(*found[0])
                return {**self.ref(node_id, member)}
            href = object_path(f"explore:{member.replace('.', ':', 1)}") if found else None
            return {"text": member, "href": href, "mark": None, "kind": None}
        return {"text": str(member), "href": None, "mark": None, "kind": None}

    # --- verdict -----------------------------------------------------------------------

    def explore_verdict(self, obj: Mapping[str, Any]) -> tuple[dict[str, str], list[str]]:
        model = obj["details"]["model"]
        explore = obj["id"].removeprefix(f"explore:{model}:")
        explore_slice = build_explore_slice(self.wb.graph, model, explore)
        verdict = deterministic_verdict(explore_slice)
        return (
            {
                "label": verdict.verdict.upper(),
                "why": verdict.rationale,
                "cls": VERDICT_CLASS.get(verdict.verdict, "muted"),
            },
            list(verdict.evidence_ids),
        )

    def roadmap_verdict(self, obj: Mapping[str, Any]) -> tuple[dict[str, str], list[str]]:
        items = list(self._roadmap.get(obj["id"], ()))
        if obj["kind"] == "table":  # column drift sits on the field; its evidence names the table
            marker = "schema_table:" + obj["name"]
            items += [
                i
                for r in self._roadmap.values()
                for i in r
                if marker in i["evidence_ids"] and not any(i is j for j in items)
            ]
        if not items:
            return (
                {
                    "label": "NO ACTION",
                    "why": "No cleanup action is queued for this object.",
                    "cls": "muted",
                },
                [],
            )
        item = items[0]
        why = "Queued in the cleanup roadmap."
        if len(items) > 1:
            why = f"{len(items)} cleanup actions are queued for this object."
        evidence = sorted({e for i in items for e in i["evidence_ids"]})
        return (
            {
                "label": ACTION_LABELS[item["action"]].upper(),
                "why": why,
                "cls": VERDICT_CLASS[item["action"]],
            },
            evidence,
        )

    # --- one object --------------------------------------------------------------------

    def object_page(self, obj: Mapping[str, Any], rows: Mapping[str, TriageRow]) -> dict[str, Any]:
        kind = obj["kind"]
        if kind == "explore":
            verdict, evidence_ids = self.explore_verdict(obj)
        else:
            verdict, evidence_ids = self.roadmap_verdict(obj)
        finding_ids = self.wb.findings_by_node.get(obj["id"], ())
        records = [r for i in finding_ids for r in self.wb.findings_by_id.get(i, ())]
        for record in records:  # evidence on this object's findings joins the roadmap's
            evidence_ids = [*evidence_ids, *record["evidence_ids"]]
        evidence_ids = list(dict.fromkeys(evidence_ids))
        loc = obj["source_file"]
        if loc and obj["source_line"]:
            loc = f"{loc}:{obj['source_line']}"
        return {
            "kind": kind,
            "kind_label": KIND_LABELS[kind],
            "node_id": obj["id"],
            "name": obj["name"],
            "loc": loc,
            "verdict": verdict,
            "evidence": self.evidence(evidence_ids),
            "facts": self._facts(obj),
            "sql": obj["details"].get("sql") if kind == "field" else None,
            "content": self._content(obj) if kind == "explore" else None,
            "upstream": [self.group(k, v) for k, v in obj["upstream"].items()],
            "downstream": [
                self.group(k, v) for k, v in obj["downstream"].items() if k != "content"
            ],
            "findings": [self.card(r, rows) for r in records],
            "records": records,
            "side_title": f"Findings on this object · {len(records)}",
        }

    def _facts(self, obj: Mapping[str, Any]) -> list[tuple[str, str]]:
        kind, details, cov = obj["kind"], obj["details"], obj["coverage"]
        if kind == "explore":
            facts: list[tuple[str, str]] = []
            usage = self.wb.graph.metadata.get("l1", {}).get("explore_usage", {}).get(obj["name"])
            if not cov["usage_checked"]:
                facts.append(("Queries", "not loaded"))
            else:
                facts.append(("Queries", str((usage or {}).get("query_count", 0))))
                facts.append(("Last queried", str((usage or {}).get("last_queried_at") or "never")))
            facts += [
                ("Model", str(details["model"])),
                ("Views joined", str(len(details["joins"]))),
            ]
            return facts
        if kind == "view":
            return [("Fields", str(details["field_count"]))]
        if kind == "pdt":
            ledger = details.get("ledger")
            if not ledger:
                return [("Build ledger", "not loaded")]
            if ledger["status"] == "missing_build_facts":  # zeros here are placeholders
                return [
                    ("Status", "missing_build_facts"),
                    ("Build facts", "not loaded for this PDT"),
                ]
            builds = ledger["build_count"]
            cost = ledger["estimated_cost_usd"]
            return [
                ("Status", str(ledger["status"])),
                ("Estimated cost", usd(cost)),
                ("Builds", f"{builds:,}"),
                ("Cost per build", usd(cost / builds) if builds else "none"),
            ]
        if kind == "field":
            return [("Type", str(details.get("type") or "unknown"))]
        return []

    def _content(self, obj: Mapping[str, Any]) -> dict[str, Any]:
        """Content usage for an explore. `not loaded` is never shown as a count of 0."""
        content = obj["content"]
        if content is None or not obj["coverage"]["content_checked"]:
            return {
                "loaded": False,
                "note": "Content usage not loaded: no content-reference facts were supplied, "
                "so this says nothing about whether content uses the explore.",
            }
        return {
            "loaded": True,
            "window": content["window_label"],
            "count": content["reference_count"],
            "by_type": sorted(content["by_type"].items()),
            "items": [
                {"title": str(i.get("title") or i["content_id"]), "type": str(i["content_type"])}
                for i in content["items"][:SHOWN]
            ],
            "more": max(0, len(content["items"]) - SHOWN),
        }

    # --- finding -----------------------------------------------------------------------

    def finding_page(
        self, finding_id: str, records: Sequence[Mapping[str, Any]], rows: Mapping[str, TriageRow]
    ) -> dict[str, Any]:
        entries = []
        for record in records:
            subject = None
            if record["subject_id"]:
                subject = {**self.ref(record["subject_id"]), "text": record["subject_id"]}
            loc = record["source_file"]
            if loc and record["source_line"]:
                loc = f"{loc}:{record['source_line']}"
            action = CATEGORY_ACTIONS.get(record["category"], "")
            entries.append(
                {
                    **self.card(record, rows),
                    "loc": loc,
                    "evidence": self.evidence(record["evidence_ids"]),
                    "subject": subject,
                    "cost": usd(record["cost_usd"]) if record.get("cost_usd") is not None else None,
                    "suggested": ACTION_LABELS.get(action),
                }
            )
        first = entries[0]
        action = CATEGORY_ACTIONS.get(records[0]["category"], "")
        verdict = {
            "label": (ACTION_LABELS.get(action) or "Integrity failure").upper(),
            "why": records[0]["message"],
            "cls": VERDICT_CLASS.get(action, "muted"),
        }
        return {
            "kind_label": "Finding",
            "node_id": None,
            "name": finding_id,
            "loc": first["loc"],
            "verdict": verdict,
            "entries": entries,
            "cards": [self.card(r, rows) for r in records],
            "side_title": f"Triage · {len(records)} record{'s' if len(records) != 1 else ''}",
        }
