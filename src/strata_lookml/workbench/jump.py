"""Jump-to-anything: the one index behind ⌘K and `/search`, and the fuzzy match over it.

`jump_index` lists every object with a page (explores, views, PDTs, tables, fields) and every
current finding, as `{id, kind, label, path}`. The browser fetches it once from
`/api/index.json` and matches as you type; `/search?q=` runs `search` over the same items on
the server, so the palette and its no-JS twin answer from one list. `fuzzy` here and
`fuzzyMatch` in assets/js/workbench.js are the same scorer (tests/test_workbench_graph.py runs
both over the same queries and compares).
"""

from __future__ import annotations

import re
from typing import Any

from strata_lookml.ir.types import explore_key
from strata_lookml.links import finding_path, object_path
from strata_lookml.workbench.index import Workbench

# Display name per index kind; served beside the items so the palette never hard-codes it.
KIND_LABELS = {
    "explore": "Explore",
    "view": "View",
    "pdt": "PDT",
    "physical_table": "Warehouse table",
    "field": "Field",
    "finding": "Finding",
}
SEARCH_LIMIT = 50
_BOUNDARY = re.compile(r"[._:\s]")


def jump_index(wb: Workbench) -> list[dict[str, str]]:
    """Every object page, then every current finding, each `{id, kind, label, path}`.

    Objects sort by kind (in `KIND_LABELS` order) then label; findings by id. `id` is the IR
    node id or the finding id; `label` is what a person types (an explore's `model.explore`).
    """
    order = list(KIND_LABELS)
    objects = []
    for node in wb.graph.nodes.values():
        path = object_path(node.id)
        if path is None or node.kind not in KIND_LABELS:
            continue
        label = (
            explore_key(str(node.attrs.get("model", "")), node.name)
            if node.kind == "explore"
            else node.name
        )
        objects.append({"id": node.id, "kind": node.kind, "label": label, "path": path})
    objects.sort(key=lambda o: (order.index(o["kind"]), o["label"], o["id"]))
    findings = [
        {"id": i, "kind": "finding", "label": i, "path": finding_path(i)}
        for i in sorted(wb.findings_by_id)
    ]
    return objects + findings


def fuzzy(query: str, text: str) -> tuple[float, list[int]] | None:
    """Score `text` against `query`, or None when it does not match.

    A case-insensitive substring wins (earlier and shorter rank higher). Otherwise the query,
    spaces dropped, must appear in order: consecutive characters and characters starting a
    word (after `.`, `_`, `:` or a space) score more. Returns the matched character offsets.
    """
    q, t = query.lower(), text.lower()
    if not q:
        return 0.0, []
    at = t.find(q)
    if at >= 0:
        return 1000 - at - len(text) * 0.1, list(range(at, at + len(q)))
    q = re.sub(r"\s+", "", q)
    score, last, hits = 0, -2, []
    qi = 0
    for i, ch in enumerate(t):
        if qi == len(q):
            break
        if ch == q[qi]:
            score += (8 if i == last + 1 else 1) + (5 if i == 0 or _BOUNDARY.match(t[i - 1]) else 0)
            hits.append(i)
            last = i
            qi += 1
    return (score - len(text) * 0.1, hits) if qi == len(q) else None


def search(
    items: list[dict[str, str]], query: str, limit: int = SEARCH_LIMIT
) -> tuple[list[dict[str, Any]], int]:
    """The best `limit` items for `query` (score descending, index order on ties) and how many
    matched in all. Each result is the item plus `hits` (matched offsets in its label)."""
    if not query.strip():
        return [], 0
    scored = [
        (m, n, item) for n, item in enumerate(items) if (m := fuzzy(query.strip(), item["label"]))
    ]
    scored.sort(key=lambda s: (-s[0][0], s[1]))
    return [{**item, "hits": m[1]} for m, _, item in scored[:limit]], len(scored)


def segments(label: str, hits: list[int]) -> list[tuple[str, bool]]:
    """`label` cut into runs of (text, matched) for highlighting the hit characters."""
    marked = set(hits)
    runs: list[tuple[str, bool]] = []
    for i, ch in enumerate(label):
        hit = i in marked
        if runs and runs[-1][1] == hit:
            runs[-1] = (runs[-1][0] + ch, hit)
        else:
            runs.append((ch, hit))
    return runs
