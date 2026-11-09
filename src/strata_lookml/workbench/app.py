"""The workbench route table: pure handlers from a request to a `Response`.

No socket code here (`server.py` adapts `http.server` to `App.respond`), so every route, header
and error page is testable without a port. Order per request: Host allow-list, then method
(GET/HEAD only until the triage POST lands), then routing. Every response, errors included,
carries `SECURITY_HEADERS`. Findings is the triage list (S5, `pages/findings.py`); the other
pages are placeholders until their own slices (S6-S8) replace them. The URL scheme, resolution
and error contract here are final.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache, cached_property
from http import HTTPStatus
from importlib import resources
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from strata_lookml.errors import InvalidInput, NotFound, StrataError
from strata_lookml.identifiers import explore_matches, explores_by_key, table_matches
from strata_lookml.ir.types import explore_id, explore_key
from strata_lookml.links import finding_path, object_path
from strata_lookml.mcp.tools import strata_object
from strata_lookml.outputs.dashboard import _embed_json, _palette_css
from strata_lookml.triage import TriageStore, triage_rows
from strata_lookml.workbench.index import Staleness, Workbench
from strata_lookml.workbench.pages.findings import findings_context, parse_query
from strata_lookml.workbench.render import render

SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    (
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "frame-ancestors 'none'",
    ),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Cache-Control", "no-store"),
)
ALLOWED_METHODS = ("GET", "HEAD")
HTML = "text/html; charset=utf-8"

# Published name -> packaged asset. Fixed: a /static/ request is a dictionary lookup, never a
# filesystem path, so no request can name a file outside this map.
STATIC_ASSETS: Mapping[str, tuple[str, str]] = {
    "cytoscape.min.js": ("strata_lookml.assets.js", "cytoscape.min.js"),
    "dagre.min.js": ("strata_lookml.assets.js", "dagre.min.js"),
    "cytoscape-dagre.min.js": ("strata_lookml.assets.js", "cytoscape-dagre.min.js"),
    "workbench.js": ("strata_lookml.assets.js", "workbench.js"),
    "workbench.css": ("strata_lookml.assets.css", "workbench.css"),
}
_STATIC_TYPES = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8"}

# URL kind -> strata_object kind (the same names, listed so the route table is explicit).
_OBJECT_ROUTES = ("explore", "view", "pdt", "table", "field")


@dataclass(frozen=True)
class Response:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes


def _response(
    status: int, body: bytes, content_type: str, extra: tuple[tuple[str, str], ...] = ()
) -> Response:
    headers = (
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        *extra,
        *SECURITY_HEADERS,
    )
    return Response(status, headers, body)


def bare_error(status: int) -> Response:
    """A plain-text error for a request whose Host was not checked or was refused.

    Never renders a page: pages carry the per-process token, which only an allow-listed Host
    may read.
    """
    phrase = HTTPStatus(status).phrase
    return _response(status, f"{status} {phrase}\n".encode(), "text/plain; charset=utf-8")


@cache
def _static_body(name: str) -> bytes:
    package, resource = STATIC_ASSETS[name]
    return (resources.files(package) / resource).read_bytes()


class App:
    """The routes for one bound server: `hosts` is the allow-list for its port."""

    def __init__(
        self, workbench: Workbench, hosts: frozenset[str], token: str, staleness: Staleness
    ) -> None:
        self.workbench = workbench
        self.hosts = hosts
        self.token = token
        self.staleness = staleness
        self._pages: dict[str, Callable[[Mapping[str, list[str]]], Response]] = {
            "/findings": self._findings,
            "/overview": self._overview,
            "/graph": self._graph,
            "/search": self._search,
            "/api/index.json": self._api_index,
        }

    # --- dispatch ----------------------------------------------------------------------

    def respond(self, method: str, target: str, host: str | None) -> Response:
        if (host or "").strip().lower() not in self.hosts:
            return bare_error(403)
        if method not in ALLOWED_METHODS:
            return self._error(
                HTTPStatus.METHOD_NOT_ALLOWED,
                StrataError(f"{method} is not supported.", hint="The workbench is read-only."),
                extra=(("Allow", ", ".join(ALLOWED_METHODS)),),
            )
        try:
            return self._route(target)
        except NotFound as exc:
            return self._error(HTTPStatus.NOT_FOUND, exc)
        except InvalidInput as exc:
            return self._error(HTTPStatus.BAD_REQUEST, exc)

    def _route(self, target: str) -> Response:
        parts = urlsplit(target)
        path, query = parts.path, parse_qs(parts.query)
        if path == "/":
            return _response(
                HTTPStatus.FOUND, b"", "text/plain; charset=utf-8", (("Location", "/findings"),)
            )
        if path in self._pages:
            return self._pages[path](query)
        segments = path.split("/")
        # Exactly `/<kind>/<one segment>`: a raw `/` inside a name arrives as %2F (links.py
        # quotes with safe=""), so `..` or extra segments never reach a lookup as a path.
        if len(segments) == 3 and segments[0] == "" and segments[2]:
            kind, name = segments[1], unquote(segments[2])
            if kind in _OBJECT_ROUTES:
                return self._object(kind, name)
            if kind == "finding":
                return self._finding(name)
            if kind == "static":
                return self._static(name)
        raise NotFound(f"no workbench page at {path}", hint="Start at /findings.")

    # --- rendering ---------------------------------------------------------------------

    def _period(self) -> Mapping[str, Any]:
        """The usage window (`{start, end, days}`) the usage facts cover, or {}."""
        return self.workbench.graph.metadata.get("l1", {}).get("period") or {}

    def _coverage(self) -> list[tuple[bool, str]]:
        """The coverage strip: (ran, text) per check, the baseline, and the analysed git ref."""
        wb = self.workbench
        cov = wb.coverage
        period = self._period()
        usage = "usage ✓"
        if period.get("days"):
            usage += f" {period['days']}d"
            if period.get("start") and period.get("end"):
                usage += f" ({period['start']} → {period['end']})"
        strip = [
            (bool(cov.get("usage")), usage if cov.get("usage") else "usage not run"),
            (bool(cov.get("schema")), "schema ✓" if cov.get("schema") else "schema not run"),
            (bool(cov.get("content")), "content ✓" if cov.get("content") else "content not loaded"),
            (
                bool(wb.baseline_path),
                f"baseline {wb.baseline_path}" if wb.baseline_path else "no baseline",
            ),
        ]
        if wb.source:
            ref = f"{str(wb.source.get('commit', ''))[:7]} on {wb.source.get('branch')}"
            strip.append(
                (not wb.source.get("dirty"), ref + (" (dirty)" if wb.source.get("dirty") else ""))
            )
        return strip

    def _context(self, title: str, nav: str = "") -> dict[str, Any]:
        return {
            "title": title,
            "nav": nav,
            "repo_name": self.workbench.repo.name,
            # NODE_PALETTE/EDGE_PALETTE as --n-*/--e-* properties: never hand-copied into CSS.
            "palette_css": _palette_css(),
            "token": self.token,
            "stale": self.staleness.stale(),
            "coverage": self._coverage(),
        }

    def _page(
        self,
        template: str,
        title: str,
        status: int = HTTPStatus.OK,
        nav: str = "",
        **context: Any,
    ) -> Response:
        body = render(template, **self._context(title, nav), **context).encode("utf-8")
        return _response(status, body, HTML)

    def _error(
        self, status: HTTPStatus, error: StrataError, extra: tuple[tuple[str, str], ...] = ()
    ) -> Response:
        body = render(
            "error.html",
            **self._context(f"{status.value} {status.phrase}"),
            status=status.value,
            reason=status.phrase,
            message=error.message,
            hint=error.hint,
        ).encode("utf-8")
        return _response(status, body, HTML, extra)

    def _placeholder(
        self,
        title: str,
        summary: str,
        facts: list[tuple[str, str]] | None = None,
        links: list[tuple[str, str]] | None = None,
    ) -> Response:
        return self._page(
            "placeholder.html",
            title,
            heading=title,
            summary=summary,
            facts=facts or [],
            links=links or [],
        )

    def _finding_links(self, ids: Any) -> list[tuple[str, str]]:
        return [(finding_path(i), i) for i in ids]

    # --- pages ----------------------------------------------------------------------------

    @cached_property
    def _store(self) -> TriageStore:
        return TriageStore.open(self.workbench.repo, self.workbench.graph)

    def _findings(self, query: Mapping[str, list[str]]) -> Response:
        wb = self.workbench
        parsed = parse_query(query)
        baseline = None if wb.baseline is None else {k: set(v) for k, v in wb.baseline.items()}
        # Read per request: an ack from `strata ack` shows on the next reload.
        rows = triage_rows(wb.graph, baseline, self._store)
        costs = {r["id"]: float(r["cost_usd"]) for r in wb.records if r.get("cost_usd") is not None}
        period = self._period()
        context = findings_context(
            rows,
            parsed,
            costs=costs,
            days=period.get("days"),
            base_url=wb.base_url,
            repo_name=wb.repo.name,
        )
        return self._page("findings.html", "Findings", nav="findings", **context)

    def _overview(self, query: Mapping[str, list[str]]) -> Response:
        wb = self.workbench
        counts = wb.graph.node_counts()
        facts = [(kind, str(n)) for kind, n in counts.items()]
        if wb.source:
            facts.append(("commit", str(wb.source.get("commit"))))
            facts.append(("branch", str(wb.source.get("branch"))))
        return self._placeholder(
            "Overview", f"{wb.repo.name}: {len(wb.records)} findings.", facts=facts
        )

    def _graph(self, query: Mapping[str, list[str]]) -> Response:
        focus = query.get("focus", [""])[0]
        return self._placeholder(
            "Graph", "The graph view arrives in a later release.", facts=[("focus", focus)]
        )

    def _search(self, query: Mapping[str, list[str]]) -> Response:
        q = query.get("q", [""])[0]
        return self._placeholder(
            "Search", "Search arrives in a later release.", facts=[("query", q)]
        )

    def _api_index(self, query: Mapping[str, list[str]]) -> Response:
        objects = [
            {"kind": node.kind, "name": node.name, "path": path}
            for node in self.workbench.graph.nodes.values()
            if (path := object_path(node.id)) is not None
        ]
        findings = [{"id": i, "path": finding_path(i)} for i in self.workbench.findings_by_id]
        body = _embed_json({"objects": objects, "findings": findings}).encode("utf-8")
        return _response(HTTPStatus.OK, body, "application/json; charset=utf-8")

    def _object(self, kind: str, name: str) -> Response:
        graph = self.workbench.graph
        keyed = explores_by_key(graph, name) if kind == "explore" else []
        if len(keyed) > 1:
            return self._candidates_page(
                kind, name, f"{name} names {len(keyed)} explores.", self._links(keyed)
            )
        try:
            if keyed:
                # The canonical `model.explore` key links.py publishes: exact, never re-split.
                ((model, explore),) = keyed
                obj = strata_object(graph, kind, explore, model=model)
            else:  # a hand-typed name: the shorthand rules every surface shares
                obj = strata_object(graph, kind, name)
        except InvalidInput as exc:
            candidates = self._candidates(kind, name)
            if not candidates:
                raise
            return self._candidates_page(kind, name, exc.message, candidates)
        facts = [("kind", obj["kind"]), ("id", obj["id"])]
        if obj["source_file"]:
            line = obj["source_line"]
            facts.append(
                ("defined in", f"{obj['source_file']}:{line}" if line else obj["source_file"])
            )
        return self._placeholder(
            f"{kind} {obj['name']}",
            "The detail page arrives in a later release.",
            facts=facts,
            links=self._finding_links(self.workbench.findings_by_node.get(obj["id"], ())),
        )

    def _candidates_page(
        self, kind: str, name: str, message: str, links: list[tuple[str, str]]
    ) -> Response:
        return self._page(
            "candidates.html",
            f"{kind} {name}",
            HTTPStatus.MULTIPLE_CHOICES,
            heading=f"Which {kind}?",
            message=message,
            links=links,
        )

    @staticmethod
    def _links(explores: list[tuple[str, str]]) -> list[tuple[str, str]]:
        named = sorted((explore_id(m, e), explore_key(m, e)) for m, e in explores)
        return [(path, label) for node_id, label in named if (path := object_path(node_id))]

    def _candidates(self, kind: str, name: str) -> list[tuple[str, str]]:
        """Links to each object an ambiguous name can mean (explores and tables only)."""
        graph = self.workbench.graph
        if kind == "explore":
            links = self._links(explore_matches(graph, name))
        elif kind == "table":
            tables = sorted(table_matches(graph, name))
            links = [(p, t) for t in tables if (p := object_path(f"physical_table:{t}"))]
        else:
            return []
        return links if len(links) > 1 else []

    def _finding(self, finding_id: str) -> Response:
        records = self.workbench.findings_by_id.get(finding_id)
        if not records:
            raise NotFound(
                f"finding not found: {finding_id}",
                hint="It may be fixed, or its category was not run. The findings list shows "
                "every current id.",
            )
        facts: list[tuple[str, str]] = []
        for record in records:
            facts.append(("category", record["category"]))
            facts.append(("message", record["message"]))
            if record["source_file"]:
                line = record["source_line"]
                facts.append(
                    (
                        "defined in",
                        f"{record['source_file']}:{line}" if line else record["source_file"],
                    )
                )
        links = []
        for record in records:
            path = object_path(record["subject_id"]) if record["subject_id"] else None
            if path is not None:
                links.append((path, record["subject_id"]))
        return self._placeholder(
            f"finding {finding_id}",
            f"{len(records)} record(s). The finding page arrives in a later release.",
            facts=facts,
            links=links,
        )

    def _static(self, name: str) -> Response:
        if name not in STATIC_ASSETS:
            raise NotFound(f"no static asset named {name}", hint="Static assets are fixed.")
        suffix = name[name.rfind(".") :]
        return _response(HTTPStatus.OK, _static_body(name), _STATIC_TYPES[suffix])
