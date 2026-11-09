"""The Findings landing page: `triage_rows` filtered, grouped and paged into a template context.

Status is never derived here: every row's status comes from `triage.triage_rows`. This module
only groups rows for display, filters them by the query string and pages them, so the page
works without JavaScript (tabs, category chips and pages are plain links; the filter is a GET
form). `workbench.js` adds the keyboard map on top of the same markup.

Grouping (M2): a PDT whose explores are all dead is reported twice, as `dead:view:<pdt>` (dead
code) and `pdt:<pdt>` (zombie or unused PDT). When both are in the same status they are one list
item carrying both ids and both category chips; ids are unchanged and actions fan out to both.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from strata_lookml.errors import InvalidInput
from strata_lookml.gate import FINDING_CATEGORIES, INTEGRITY
from strata_lookml.links import finding_path
from strata_lookml.triage import TriageRow
from strata_lookml.workbench.pr_text import CATEGORY_LABELS, usd

PAGE_SIZE = 200

# (query value, tab label); `1`-`6` select them in order.
STATUS_TABS: tuple[tuple[str, str], ...] = (
    ("new", "New"),
    ("acknowledged", "Acknowledged"),
    ("baselined", "Baselined"),
    ("fixed", "Fixed"),
    ("not_checked", "Not checked"),
    ("all", "All"),
)
STATUS_LABELS = {
    "new": "new",
    "acknowledged": "ack",
    "baselined": "baselined",
    "fixed": "fixed",
    "not_checked": "not checked",
}
CATEGORIES = (INTEGRITY, *FINDING_CATEGORIES)
_PDT_CATEGORIES = ("zombie-pdt", "unused-pdt")
_DEAD_VIEW = "dead:view:"


@dataclass(frozen=True)
class Item:
    """One list row: a single finding, or a PDT's dead-code and PDT findings together (M2)."""

    rows: tuple[TriageRow, ...]

    @property
    def status(self) -> str:
        return self.rows[0].status

    @property
    def categories(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(r.category for r in self.rows))

    def matches(self, category: str, q: str) -> bool:
        if category != "all" and category not in self.categories:
            return False
        if not q:
            return True
        return any(
            q in r.id.lower() or q in r.label.lower() or q in (r.source_file or "").lower()
            for r in self.rows
        )


def _pdt_name(row: TriageRow) -> str | None:
    """The PDT a row is about, when it is one half of the M2 pair."""
    if row.category == "dead-code" and row.id.startswith(_DEAD_VIEW):
        return row.id.removeprefix(_DEAD_VIEW)
    if row.category in _PDT_CATEGORIES and row.id.startswith("pdt:"):
        return row.id.removeprefix("pdt:")
    return None


def group_rows(rows: Sequence[TriageRow]) -> list[Item]:
    """`rows` as list items, in `rows` order; a group sits where its first member was.

    A PDT's `dead:view:` and `pdt:` rows group only when both exist in the same status, so a
    group is never split across tabs and its status is its members' status.
    """
    halves: dict[tuple[str, str], list[int]] = {}
    for index, row in enumerate(rows):
        name = _pdt_name(row)
        if name is not None:
            halves.setdefault((name, row.status), []).append(index)
    partner: dict[int, int] = {}
    for indexes in halves.values():
        kinds = {rows[i].category == "dead-code" for i in indexes}
        if len(indexes) == 2 and kinds == {True, False}:
            first, second = indexes
            partner[first] = second
            partner[second] = first
    items: list[Item] = []
    placed: set[int] = set()
    for index, row in enumerate(rows):
        if index in placed:
            continue
        other = partner.get(index)
        if other is None:
            items.append(Item((row,)))
            continue
        placed.add(other)
        # The PDT finding leads: its label is the PDT and it carries the cost.
        pair = (rows[other], row) if row.category == "dead-code" else (row, rows[other])
        items.append(Item(pair))
    return items


@dataclass(frozen=True)
class Query:
    status: str
    category: str
    q: str
    page: int


def parse_query(query: Mapping[str, list[str]]) -> Query:
    """The filters from the query string; an unknown value is `InvalidInput` (a 400 page)."""

    def one(key: str, default: str) -> str:
        return (query.get(key) or [default])[0].strip() or default

    status, category, page = one("status", "new"), one("category", "all"), one("page", "1")
    if status not in dict(STATUS_TABS):
        raise InvalidInput(
            f"unknown status: {status}", hint="Use one of: " + ", ".join(k for k, _ in STATUS_TABS)
        )
    if category != "all" and category not in CATEGORIES:
        raise InvalidInput(
            f"unknown category: {category}", hint="Use one of: all, " + ", ".join(CATEGORIES)
        )
    if not page.isdigit() or int(page) < 1:
        raise InvalidInput(f"page must be a positive number, not {page}")
    return Query(status, category, (query.get("q") or [""])[0].strip(), int(page))


def findings_href(status: str, category: str = "all", q: str = "", page: int = 1) -> str:
    """The `/findings` URL for a filter state (defaults left out, status always explicit)."""
    params = {"status": status}
    if category != "all":
        params["category"] = category
    if q:
        params["q"] = q
    if page > 1:
        params["page"] = str(page)
    return "/findings?" + urlencode(params)


def _location(row: TriageRow) -> str | None:
    if not row.source_file:
        return None
    return f"{row.source_file}:{row.source_line}" if row.source_line else row.source_file


def findings_context(
    rows: Sequence[TriageRow],
    query: Query,
    *,
    costs: Mapping[str, float],
    days: int | None,
) -> dict[str, Any]:
    """The template context for one `/findings` request."""
    items = group_rows(rows)
    needle = query.q.lower()

    def counted(status: str, category: str) -> int:
        return sum(
            1
            for item in items
            if (status == "all" or item.status == status) and item.matches(category, needle)
        )

    tabs = [
        {
            "key": key,
            "label": label,
            "count": counted(key, query.category),
            "href": findings_href(key, query.category, query.q),
            "current": key == query.status,
        }
        for key, label in STATUS_TABS
    ]
    chips = [
        {
            "key": key,
            "label": "All categories" if key == "all" else CATEGORY_LABELS[key],
            "count": counted(query.status, key),
            "href": findings_href(query.status, key, query.q),
            "current": key == query.category,
        }
        for key in ("all", *CATEGORIES)
    ]
    shown = [
        item
        for item in items
        if (query.status == "all" or item.status == query.status)
        and item.matches(query.category, needle)
    ]
    pages = max(1, math.ceil(len(shown) / PAGE_SIZE))
    page = min(query.page, pages)
    start = (page - 1) * PAGE_SIZE
    listed = [_item_context(item, costs) for item in shown[start : start + PAGE_SIZE]]
    return {
        "query": query,
        "tabs": tabs,
        "chips": chips,
        "items": listed,
        "shown": len(shown),
        "total": len(items),
        "first": start + 1 if listed else 0,
        "last": start + len(listed),
        "page": page,
        "pages": [
            {"number": n, "href": findings_href(query.status, query.category, query.q, n)}
            for n in range(1, pages + 1)
        ]
        if pages > 1
        else [],
        "cost_heading": f"Cost / {days}d" if days else "Cost",
        "empty": _empty_message(query),
    }


def _item_context(item: Item, costs: Mapping[str, float]) -> dict[str, Any]:
    lead = item.rows[0]
    current = lead.status not in ("fixed", "not_checked")
    cost = next((costs[r.id] for r in item.rows if r.id in costs), None)
    locations = list(dict.fromkeys(loc for r in item.rows if (loc := _location(r))))
    return {
        # Multi-value attributes are JSON arrays: an id or a path may contain a space or a
        # newline, so the page script parses them and never splits text.
        "ids_json": json.dumps([r.id for r in item.rows]),
        "chips": [(c, CATEGORY_LABELS[c]) for c in item.categories],
        "label": lead.label,
        "title": "\n".join(r.id for r in item.rows),
        "message": lead.message,
        # A fixed or not-checked id has no current record, so no finding page to open.
        "href": finding_path(lead.id) if current else None,
        "also": [
            {"label": r.id, "href": finding_path(r.id) if current else None} for r in item.rows[1:]
        ],
        "location": locations[0] if locations else None,
        "locations": "\n".join(locations),
        "locations_json": json.dumps(locations),
        "cost": usd(cost) if cost is not None else None,
        "status": lead.status,
        "status_label": STATUS_LABELS[lead.status],
    }


def _empty_message(query: Query) -> tuple[str, str]:
    if query.q:
        return (f"No findings match “{query.q}”", "Clear the filter, or look under All.")
    if query.status == "new":
        return ("Nothing new to triage", "Every current finding is acknowledged or baselined.")
    if query.status == "not_checked":
        return ("Every category was checked", "No stored finding is waiting on a skipped check.")
    return ("No findings in this view", "Switch tab with 1–6 or category with f.")
