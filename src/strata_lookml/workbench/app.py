"""The workbench route table: pure handlers from a request to a `Response`.

No socket code here (`server.py` adapts `http.server` to `App.respond`), so every route, header
and error page is testable without a port. Order per request: Host allow-list, then method
(GET/HEAD everywhere except `POST /api/triage`, the one write: `_triage_post`), then routing.
Every response, errors included, carries `SECURITY_HEADERS`. Findings is the triage list (S5,
`pages/findings.py`); the other pages are placeholders until their own slices (S6-S8) replace
them. The URL scheme, resolution
and error contract here are final.
"""

from __future__ import annotations

import hmac
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from http import HTTPStatus
from importlib import resources
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from strata_lookml.errors import InvalidInput, NotFound, StrataError
from strata_lookml.identifiers import explore_matches, explores_by_key, table_matches
from strata_lookml.ir.types import explore_id, explore_key
from strata_lookml.links import finding_path, object_path
from strata_lookml.mcp.tools import strata_object
from strata_lookml.outputs.artifacts import cleanup_roadmap
from strata_lookml.outputs.dashboard import _embed_json, _palette_css
from strata_lookml.triage import TriageRow, TriageStore, triage_rows
from strata_lookml.workbench.detail import Detail
from strata_lookml.workbench.index import Staleness, Workbench
from strata_lookml.workbench.overview import overview_context
from strata_lookml.workbench.pages.findings import STATUS_LABELS, findings_context, parse_query
from strata_lookml.workbench.pr_text import pr_comment
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
JSON = "application/json; charset=utf-8"
TRIAGE_PATH = "/api/triage"
MAX_TRIAGE_BODY = 64 * 1024

# Published name -> packaged asset. Fixed: a /static/ request is a dictionary lookup, never a
# filesystem path, so no request can name a file outside this map.
STATIC_ASSETS: Mapping[str, tuple[str, str]] = {
    "cytoscape.min.js": ("strata_lookml.assets.js", "cytoscape.min.js"),
    "dagre.min.js": ("strata_lookml.assets.js", "dagre.min.js"),
    "cytoscape-dagre.min.js": ("strata_lookml.assets.js", "cytoscape-dagre.min.js"),
    "workbench.js": ("strata_lookml.assets.js", "workbench.js"),
    "workbench.css": ("strata_lookml.assets.css", "workbench.css"),
    "detail.js": ("strata_lookml.assets.js", "detail.js"),
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


def _json(
    status: int, payload: Mapping[str, Any], extra: tuple[tuple[str, str], ...] = ()
) -> Response:
    return _response(status, _embed_json(payload).encode("utf-8"), JSON, extra)


_WRITE_HINT = (
    "Acknowledge from a workbench page, or use `strata ack` / `strata unack` "
    "(the no-JavaScript path)."
)


# Stable error codes (the stdlib's reason phrases differ across Python versions).
_REFUSAL_CODES = {
    HTTPStatus.BAD_REQUEST: "invalid_input",
    HTTPStatus.FORBIDDEN: "forbidden",
    HTTPStatus.METHOD_NOT_ALLOWED: "method_not_allowed",
    HTTPStatus.LENGTH_REQUIRED: "length_required",
    HTTPStatus.REQUEST_ENTITY_TOO_LARGE: "too_large",
    HTTPStatus.UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
}
_RELOAD_HINT = "Reload the page: the token changes each time the workbench starts."


class _Refused(Exception):
    """A triage request that failed a check; the store was never called."""

    def __init__(self, status: int, message: str, hint: str | None = _WRITE_HINT) -> None:
        super().__init__(message)
        self.response = _refusal(status, message, hint)


def _refusal(
    status: int,
    message: str,
    hint: str | None = _WRITE_HINT,
    extra: tuple[tuple[str, str], ...] = (),
) -> Response:
    return _json(
        status, {"error": message, "code": _REFUSAL_CODES[HTTPStatus(status)], "hint": hint}, extra
    )


def _write_request(
    host: str,
    token: str,
    headers: Iterable[tuple[str, str]],
    read: Callable[[int], bytes] | None,
) -> tuple[str, list[str], str | None]:
    """The checked `(action, ids, note)` of a triage POST, or `_Refused`.

    Every check passes before the body is read: Origin is this server's own (`http://<Host>`,
    the Host already allow-listed; missing is refused), `Sec-Fetch-Site` is same-origin when
    sent, `Content-Type` is exactly `application/json` (a cross-origin page cannot send it
    without a CORS preflight, which is never granted), `X-Strata-Token` is this process's token
    (constant time), and `Content-Length` is present and at most `MAX_TRIAGE_BODY`.
    """
    values: dict[str, list[str]] = {}
    for name, value in headers:
        values.setdefault(name.lower(), []).append(value)

    def one(name: str) -> str | None:
        got = values.get(name, [])
        if len(got) > 1:
            raise _Refused(HTTPStatus.BAD_REQUEST, f"duplicate {name} header")
        return got[0].strip() if got else None

    if one("origin") != f"http://{host}":
        raise _Refused(HTTPStatus.FORBIDDEN, "cross-origin write refused")
    if one("sec-fetch-site") not in (None, "same-origin"):
        raise _Refused(HTTPStatus.FORBIDDEN, "cross-site write refused")
    if one("content-type") != "application/json":
        raise _Refused(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")
    given = (one("x-strata-token") or "").encode("utf-8", "surrogatepass")
    if not hmac.compare_digest(given, token.encode("utf-8")):
        raise _Refused(HTTPStatus.FORBIDDEN, "missing or wrong page token", hint=_RELOAD_HINT)
    length = one("content-length")
    if one("transfer-encoding") is not None or length is None:
        raise _Refused(HTTPStatus.LENGTH_REQUIRED, "Content-Length is required")
    if not re.fullmatch(r"[0-9]+", length):
        raise _Refused(HTTPStatus.BAD_REQUEST, "Content-Length is not a number")
    if int(length) > MAX_TRIAGE_BODY:
        raise _Refused(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body over 64 KB")
    try:
        body = read(int(length)) if read else b""
    except OSError:  # the client stalled past the server's read timeout
        body = b""
    if len(body) != int(length):
        raise _Refused(HTTPStatus.BAD_REQUEST, "request body shorter than Content-Length")
    return _triage_payload(body)


def _triage_payload(body: bytes) -> tuple[str, list[str], str | None]:
    """`{"action": "ack"|"unack", "ids": [str, ...], "note"?: str}` (note with ack only)."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise _Refused(HTTPStatus.BAD_REQUEST, "request body is not JSON") from None
    if not isinstance(payload, dict) or not set(payload) <= {"action", "ids", "note"}:
        raise _Refused(HTTPStatus.BAD_REQUEST, "expected an object with action, ids, note")
    action, ids, note = payload.get("action"), payload.get("ids"), payload.get("note")
    if action not in ("ack", "unack"):
        raise _Refused(HTTPStatus.BAD_REQUEST, 'action must be "ack" or "unack"')
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and i for i in ids):
        raise _Refused(HTTPStatus.BAD_REQUEST, "ids must be a non-empty list of finding ids")
    if note is not None and (action != "ack" or not isinstance(note, str)):
        raise _Refused(HTTPStatus.BAD_REQUEST, "note must be a string, and only with ack")
    return action, list(dict.fromkeys(ids)), note


def _row_json(row: TriageRow) -> dict[str, Any]:
    """What a page needs to repaint one row after a write (its status from `triage_rows`)."""
    return {
        "id": row.id,
        "status": row.status,
        "label": STATUS_LABELS[row.status],
        "acked_at": row.acked_at,
        "note": row.note,
    }


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
        self._store = TriageStore.open(workbench.repo, workbench.graph)
        self._detail = Detail(workbench, cleanup_roadmap(workbench.graph.metadata.get("l1", {})))
        self._pages: dict[str, Callable[[Mapping[str, list[str]]], Response]] = {
            "/findings": self._findings,
            "/overview": self._overview,
            "/graph": self._graph,
            "/search": self._search,
            "/api/index.json": self._api_index,
            "/api/pr-comment": self._api_pr_comment,
        }

    # --- dispatch ----------------------------------------------------------------------

    def respond(
        self,
        method: str,
        target: str,
        host: str | None,
        headers: Iterable[tuple[str, str]] = (),
        read: Callable[[int], bytes] | None = None,
    ) -> Response:
        """`headers` and `read` (the body reader) are used only by `POST /api/triage`."""
        allowed = (host or "").strip().lower()
        if allowed not in self.hosts:
            return bare_error(403)
        if urlsplit(target).path == TRIAGE_PATH:
            return self._triage_post(method, allowed, headers, read)
        if method not in ALLOWED_METHODS:
            return self._error(
                HTTPStatus.METHOD_NOT_ALLOWED,
                StrataError(
                    f"{method} is not supported.",
                    hint="Pages are GET only; the one write is POST /api/triage.",
                ),
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

    # --- the one write: POST /api/triage -----------------------------------------------

    def _triage_post(
        self,
        method: str,
        host: str,
        headers: Iterable[tuple[str, str]],
        read: Callable[[int], bytes] | None,
    ) -> Response:
        """Acknowledge or unacknowledge from a workbench page: an adapter over `TriageStore`.

        `_write_request` refuses anything a page of this server did not send; only then is the
        store called. Every answer is JSON (`_embed_json`), never HTML, so nothing from the
        request reaches markup.
        """
        if method != "POST":
            return _refusal(
                HTTPStatus.METHOD_NOT_ALLOWED,
                f"{method} is not supported on {TRIAGE_PATH}.",
                extra=(("Allow", "POST"),),
            )
        try:
            action, ids, note = _write_request(host, self.token, headers, read)
            if action == "ack":
                self._store.acknowledge(ids, note)
            else:
                self._store.unacknowledge(ids)
        except _Refused as refused:
            return refused.response
        except InvalidInput as exc:  # an id outside the allowlist: nothing was written
            return _json(HTTPStatus.BAD_REQUEST, exc.to_dict())
        except StrataError as exc:  # concurrent writers outlasted the retries
            return _json(HTTPStatus.CONFLICT, exc.to_dict())
        rows = self._triage_rows()
        return _json(
            HTTPStatus.OK,
            {
                "rows": [_row_json(rows[i]) for i in ids if i in rows],
                "untracked": [i for i in ids if i not in rows],
            },
        )

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
        nav: str = "",
    ) -> Response:
        return self._page(
            "placeholder.html",
            title,
            nav=nav,
            heading=title,
            summary=summary,
            facts=facts or [],
            links=links or [],
        )

    def _finding_links(self, ids: Any) -> list[tuple[str, str]]:
        return [(finding_path(i), i) for i in ids]

    # --- pages ----------------------------------------------------------------------------

    def _findings(self, query: Mapping[str, list[str]]) -> Response:
        wb = self.workbench
        parsed = parse_query(query)
        rows = list(self._triage_rows().values())
        costs = {r["id"]: float(r["cost_usd"]) for r in wb.records if r.get("cost_usd") is not None}
        period = self._period()
        context = findings_context(
            rows,
            parsed,
            costs=costs,
            days=period.get("days"),
        )
        return self._page("findings.html", "Findings", nav="findings", **context)

    def _api_pr_comment(self, query: Mapping[str, list[str]]) -> Response:
        """`pr_text.pr_comment` for the current findings among `?id=...` (the list's `c`).

        The browser never formats the comment: it fetches this text and copies it, so the
        Findings list, the finding page and the detail pages share one builder.
        """
        ids = list(dict.fromkeys(query.get("id", [])))
        records = [dict(r) for i in ids for r in self.workbench.findings_by_id.get(i, ())]
        if not records:
            raise NotFound(
                "no current finding among the requested ids",
                hint="Fixed and not-checked findings have no record to comment on.",
            )
        subject = {"kind": "finding", "id": "", "name": ""}
        text = pr_comment(records, subject, self.workbench.base_url)
        return _response(HTTPStatus.OK, text.encode("utf-8"), "text/plain; charset=utf-8")

    def _overview(self, query: Mapping[str, list[str]]) -> Response:
        return self._page(
            "overview.html", "Overview", nav="overview", **overview_context(self.workbench)
        )

    def _graph(self, query: Mapping[str, list[str]]) -> Response:
        focus = query.get("focus", [""])[0]
        return self._placeholder(
            "Graph",
            "The graph view arrives in a later release.",
            facts=[("focus", focus)],
            nav="graph",
        )

    def _search(self, query: Mapping[str, list[str]]) -> Response:
        q = query.get("q", [""])[0]
        return self._placeholder(
            "Search", "Search arrives in a later release.", facts=[("query", q)], nav="search"
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
        page = self._detail.object_page(obj, self._triage_rows())
        records = page.pop("records")
        pr_text = pr_comment(
            records,
            obj,
            self.workbench.base_url,
            verdict=(page["verdict"]["label"], page["verdict"]["why"]),
        )
        return self._page("detail.html", f"{kind} {obj['name']}", pr_text=pr_text, **page)

    def _triage_rows(self) -> dict[str, TriageRow]:
        """Each finding id's triage row in `triage_rows` order, read fresh per request (an ack
        made by the CLI shows on reload). Findings, the finding page and the detail pages all
        read rows through here."""
        wb = self.workbench
        baseline = None if wb.baseline is None else {k: set(v) for k, v in wb.baseline.items()}
        return {r.id: r for r in triage_rows(wb.graph, baseline, self._store)}

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
        page = self._detail.finding_page(finding_id, records, self._triage_rows())
        subject = {"kind": "finding", "id": finding_id, "name": finding_id}
        pr_text = pr_comment(records, subject, self.workbench.base_url)
        return self._page("finding.html", f"finding {finding_id}", pr_text=pr_text, **page)

    def _static(self, name: str) -> Response:
        if name not in STATIC_ASSETS:
            raise NotFound(f"no static asset named {name}", hint="Static assets are fixed.")
        suffix = name[name.rfind(".") :]
        return _response(HTTPStatus.OK, _static_body(name), _STATIC_TYPES[suffix])
