"""The static export: the whole workbench as one self-contained, read-only HTML file.

There is no second UI. Every page in the file is what the live server returns for that route:
`export` asks a read-only `App` (no triage store, so nothing under ~/.strata is read or
written) for each route in `App.export_routes` and keeps the inside of its `<main>` byte for
byte as an inert `<template data-route>`. The shell is the same `_layout.html` with the
packaged stylesheet and scripts inlined (a file has no /static/), and `assets/js/router.js`
swaps a template into `<main>` per `#/<route>` hash. What the live pages fetch is embedded
once through `json_script`: the ⌘K index, the graph (graph.js computes each focus
neighbourhood from it, drawn into the one focused graph page the file holds), and each
finding's PR-comment lines from `pr_text.finding_lines`.
"""

from __future__ import annotations

import base64
import hashlib
import html
import math
import re
from collections.abc import Mapping
from importlib import resources
from typing import Any

from strata_lookml.links import object_path
from strata_lookml.workbench.app import App
from strata_lookml.workbench.detail import KIND_LABELS
from strata_lookml.workbench.graph import (
    EDGE_LEGEND,
    NODE_CAP,
    NODE_LEGEND,
    edge_var,
    export_graph_data,
    node_var,
    palette_css,
)
from strata_lookml.workbench.index import Staleness, Workbench
from strata_lookml.workbench.jump import KIND_LABELS as JUMP_KINDS
from strata_lookml.workbench.pages.findings import findings_href
from strata_lookml.workbench.pr_text import finding_lines
from strata_lookml.workbench.render import (
    inline_script,
    inline_style,
    json_script,
    page_fragment,
    render,
)

# The Host the export's `App` answers: never bound, never a real name (RFC 2606 `.invalid`).
EXPORT_HOST = "export.invalid"
# Inlined in this order: the router first, so a page is in <main> before the others run.
SCRIPTS = (
    "router.js",
    "workbench.js",
    "detail.js",
    "cytoscape.min.js",
    "dagre.min.js",
    "cytoscape-dagre.min.js",
    "graph.js",
)
# The old single-page dashboard's section anchors (`dashboard.html#drift`, ...), so a link
# copied from it still lands somewhere that answers the same question.
LEGACY_SECTIONS = {
    "graph": "/graph",
    "dead-code": findings_href("all", "dead-code"),
    "drift": findings_href("all", "drift"),
    "pdt-cost": "/overview",
    "roadmap": "/overview",
    "migration": "/overview",
}
_MAIN = re.compile(r"<main>(.*)</main>", re.DOTALL)
_TITLE = re.compile(r"<title>(.*?) · Strata workbench</title>", re.DOTALL)


def _asset(package: str, name: str) -> str:
    return (resources.files(package) / name).read_text(encoding="utf-8")


def _csp(scripts: list[str]) -> str:
    """Only these inline scripts run (by hash), and nothing is fetched: a file needs no network."""
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"
        for s in scripts
    )
    return (
        f"default-src 'none'; script-src {hashes}; style-src 'unsafe-inline'; "
        "img-src data:; base-uri 'none'; form-action 'none'"
    )


def page(app: App, route: str) -> tuple[str, str]:
    """(title, the inside of `<main>`) of the live server's answer for `route`."""
    body = app.respond("GET", route, EXPORT_HOST).body.decode("utf-8")
    main, title = _MAIN.search(body), _TITLE.search(body)
    if main is None or title is None:
        raise ValueError(f"{route} did not render a workbench page")
    return html.unescape(title.group(1)), main.group(1)


def _field_aliases(wb: Workbench, items: list[dict[str, str]]) -> dict[str, list[str]]:
    """Field page -> [its view's page, the field name]: the export has no field pages."""
    aliases = {}
    for item in items:
        if item["kind"] != "field":
            continue
        node = wb.graph.get_node(item["id"])
        view = str(node.attrs.get("view", "")) if node else ""
        target = object_path(f"view:{view}") if wb.graph.get_node(f"view:{view}") else None
        if node is not None and target:
            aliases[item["path"]] = [target, str(node.attrs.get("field_name") or node.name)]
    return aliases


def export_data(app: App) -> dict[str, Any]:
    """What the export's scripts read instead of fetching: one JSON payload."""
    wb = app.workbench
    comments: dict[str, Mapping[str, Any]] = {
        finding_id: {
            "n": len(records),
            "text": "\n".join(line for r in records for line in finding_lines(r, wb.base_url)),
        }
        for finding_id, records in wb.findings_by_id.items()
    }
    findings = findings_href("new")
    return {
        "index": {"kinds": JUMP_KINDS, "items": app.jump_items},
        "graph": export_graph_data(app.graph_data),
        "graph_kinds": KIND_LABELS,
        "cap": NODE_CAP,
        "comments": comments,
        "aliases": {"/": [findings], "/findings": [findings], **_field_aliases(wb, app.jump_items)},
        "sections": LEGACY_SECTIONS,
    }


def export(workbench: Workbench) -> str:
    """The workbench as one HTML file: no fetches, no writes, no triage controls."""
    # The export never checks staleness (a snapshot), so the fingerprint is never taken.
    staleness = Staleness(workbench.inputs, lambda: workbench.inputs, interval=math.inf)
    app = App(workbench, frozenset({EXPORT_HOST}), "", staleness, read_only=True)
    pages = []
    for route in app.export_routes():
        title, main = page(app, route)
        pages.append({"route": route, "title": title, "html": page_fragment(main)})
    sources = [_asset("strata_lookml.assets.js", name) for name in SCRIPTS]
    first = pages[0]
    return render(
        "export.html",
        title=first["title"],
        nav="",
        repo_name=workbench.repo.name,
        coverage=app.coverage(),
        csp=_csp(sources),
        stylesheet=inline_style(_asset("strata_lookml.assets.css", "workbench.css")),
        palette_css=palette_css(),
        node_legend=[(node_var(k), label) for k, label in NODE_LEGEND.items()],
        edge_legend=[(edge_var(r), label) for r, label in EDGE_LEGEND.items()],
        pages=pages,
        data=json_script(export_data(app)),
        scripts=[inline_script(s) for s in sources],
    )
