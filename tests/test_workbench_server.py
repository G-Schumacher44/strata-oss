"""Workbench router and server (workbench S4): routes, resolution, headers, Host, cache, escaping."""

from __future__ import annotations

import http.client
import http.server
import json
import socket
import threading
from collections.abc import Iterator
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path
from urllib.parse import quote

import pytest
from click.testing import CliRunner
from markupsafe import escape

from strata_lookml import pipeline
from strata_lookml.cli import dashboard as dash
from strata_lookml.cli.dashboard import allowed_hosts
from strata_lookml.cli.main import strata_cli
from strata_lookml.errors import InvalidInput
from strata_lookml.identifiers import resolve_field
from strata_lookml.links import finding_path, object_path
from strata_lookml.workbench.app import SECURITY_HEADERS, App, Response
from strata_lookml.workbench.index import Staleness, Workbench, index_graph, load_graph
from strata_lookml.workbench.server import make_handler, new_token

ROOT = Path(__file__).resolve().parent
TWIN = ROOT / "lookml" / "twin_models"
PORT = 18765  # only ever a Host string for App-level tests, never bound
HOST = f"127.0.0.1:{PORT}"
TOKEN = "test-token-not-secret"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "frame-ancestors 'none'"
)

HOSTILE = "<img src=x onerror=alert(1)>"


@pytest.fixture(autouse=True)
def _home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """The IR cache lands under ~/.strata: keep it in a temp HOME."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("STRATA_CACHE_PATH", raising=False)


def _workbench(repo: Path, usage: Path | None = None, schema: Path | None = None) -> Workbench:
    graph, inputs = load_graph(repo, str(usage) if usage else None, str(schema) if schema else None)
    return index_graph(
        graph,
        repo=repo,
        usage_fixture=str(usage) if usage else None,
        schema_fixture=str(schema) if schema else None,
        inputs=inputs,
    )


def _app(wb: Workbench) -> App:
    return App(wb, allowed_hosts(PORT), TOKEN, Staleness(wb.inputs, wb.fingerprint))


def _get(app: App, target: str, method: str = "GET", host: str | None = HOST) -> Response:
    return app.respond(method, target, host)


def _text(response: Response) -> str:
    return response.body.decode("utf-8")


@pytest.fixture
def twin() -> App:
    return _app(_workbench(TWIN))


def _hostile_repo(root: Path) -> tuple[Path, Path, Path]:
    """A LookML repo whose names, file names and table names carry markup, quotes, `%2F`, `..`,
    `%20` and a dot, plus usage and schema facts that turn them into findings."""
    repo = root / "repo"
    repo.mkdir()
    for model in (f"m{HOSTILE}", "twin"):
        (repo / f"{model}.model.lkml").write_text(
            'connection: "c"\ninclude: "*.view.lkml"\n'
            'explore: "a</script>b" { from: orders }\n'
            'explore: "dotted.name" { from: orders }\n',
            encoding="utf-8",
        )
    (repo / f"v{HOSTILE}.view.lkml").write_text(
        "view: orders {\n"
        "  sql_table_name: `p.d.\"q'<t>` ;;\n"
        "  dimension: id { sql: ${TABLE}.id ;; }\n"
        "  dimension: unit_cost { sql: ${TABLE}.unit_cost ;; }\n"
        "}\n"
        'view: "o\\"q\'<b>" {\n'
        "  derived_table: { sql: select 1 ;; datagroup_trigger: x }\n"
        '  dimension: "f</script>" { sql: 1 ;; }\n'
        "}\n"
        'view: "a%2F..b" { sql_table_name: foo%20bar ;; dimension: c { sql: ${TABLE}.c ;; } }\n'
        'view: ".." { dimension: d { sql: 1 ;; } }\n',
        encoding="utf-8",
    )
    usage = root / "usage.json"
    usage.write_text(
        json.dumps(
            {
                "explore_usage": [],
                "content_references": [],
                "pdt_builds": [
                    {
                        "view": "o\"q'<b>",
                        "build_count": 9,
                        "last_built_at": "2026-06-01T00:00:00Z",
                        "bytes_processed": 1,
                        "estimated_cost_usd": 1.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    schema = root / "schema.json"
    schema.write_text(
        json.dumps(
            {
                "tables": [
                    {"name": "p.d.\"q'<t>", "columns": ["id"]},
                    {"name": "foo%20bar", "columns": []},
                ]
            }
        ),
        encoding="utf-8",
    )
    return repo, usage, schema


@pytest.fixture
def hostile(tmp_path: Path) -> App:
    return _app(_workbench(*_hostile_repo(tmp_path)))


# --- routing and resolution ------------------------------------------------------------------


def test_root_redirects_to_findings(twin: App) -> None:
    r = _get(twin, "/")
    assert r.status == 302
    assert ("Location", "/findings") in r.headers


@pytest.mark.parametrize(
    "target", ["/findings", "/overview", "/graph?focus=x&hops=1", "/search?q=x", "/findings?page=2"]
)
def test_fixed_pages_render(twin: App, target: str) -> None:
    r = _get(twin, target)
    assert r.status == 200
    assert f'<meta name="strata-token" content="{TOKEN}">' in _text(r)


def test_api_index_lists_every_object_page(twin: App) -> None:
    r = _get(twin, "/api/index.json")
    assert ("Content-Type", "application/json; charset=utf-8") in r.headers
    paths = {o["path"] for o in json.loads(r.body)["objects"]}
    assert {"/explore/retail.orders", "/explore/wholesale.orders", "/view/accounts"} <= paths


def test_dotted_explore_key_resolves(twin: App) -> None:
    r = _get(twin, "/explore/retail.orders")
    assert r.status == 200
    assert "explore:retail:orders" in _text(r)


def test_ambiguous_explore_is_a_candidates_page(twin: App) -> None:
    r = _get(twin, "/explore/orders")
    assert r.status == 300
    body = _text(r)
    assert '<a href="/explore/retail.orders">retail.orders</a>' in body
    assert '<a href="/explore/wholesale.orders">wholesale.orders</a>' in body


def test_canonical_explore_keys_resolve_exactly(tmp_path: Path) -> None:
    """The `model.explore` key links.py publishes is matched whole: a dotted model name
    resolves, and an explore literally named `retail.orders` elsewhere never captures it."""
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "v.view.lkml").write_text("view: v { dimension: a {} }\n", encoding="utf-8")
    for model, explore in (
        ("retail", "orders"),
        ("retail.v2", "orders"),
        ("other", '"retail.orders"'),
    ):
        (repo / f"{model}.model.lkml").write_text(
            f'connection: "c"\ninclude: "*.view.lkml"\nexplore: {explore} {{ from: v }}\n',
            encoding="utf-8",
        )
    app = _app(_workbench(repo))
    for node_id in (
        "explore:retail:orders",
        "explore:retail.v2:orders",
        "explore:other:retail.orders",
    ):
        r = _get(app, object_path(node_id) or "")
        assert r.status == 200, (node_id, _text(r))
        assert f'data-node-id="{node_id}"' in _text(r)
    r = _get(app, "/explore/orders")  # hand-typed shorthand still offers both models
    assert r.status == 300
    assert '<a href="/explore/retail.v2.orders">retail.v2.orders</a>' in _text(r)


@pytest.mark.parametrize(
    ("target", "status", "message"),
    [
        ("/explore/nope", 404, "explore not found: nope"),
        ("/view/nope", 404, "view not found: nope"),
        ("/table/nope", 404, "physical_table not found in IR: nope"),
        ("/field/accounts.nope", 404, "field not found: accounts.nope"),
        ("/finding/nope", 404, "finding not found: nope"),
        ("/nowhere", 404, "no workbench page at /nowhere"),
        ("/findings/", 404, "no workbench page"),
        ("/view/a/b", 404, "no workbench page"),
        ("/field/accounts", 400, "field must be given as view.field"),
    ],
)
def test_unresolved_pages_render_the_error_contract(
    twin: App, target: str, status: int, message: str
) -> None:
    r = _get(twin, target)
    assert r.status == status
    body = _text(r)
    assert message in body
    assert '<p class="hint">' in body, "every StrataError raised here carries a hint"


def _splits(name: str) -> bool:
    try:
        resolve_field(name)
    except InvalidInput:
        return False
    return True


def test_every_object_and_finding_link_round_trips(hostile: App) -> None:
    """links.py builds each path; the router parses it back to the same object or finding."""
    graph = hostile.workbench.graph
    seen = 0
    for node in graph.nodes.values():
        path = object_path(node.id)
        if path is None:
            continue
        r = _get(hostile, path)
        if node.kind == "field" and not _splits(node.name):
            # Known gap (predates the workbench): `identifiers.resolve_field` splits
            # `view.field` at the first dot, so a field of a view named `..` has no page.
            # It must still be a clean error page, never a crash.
            assert r.status == 400 and "view.field" in _text(r), path
            continue
        assert r.status in (200, 300), (path, _text(r))
        if r.status == 200:
            assert f'data-node-id="{escape(node.id)}"' in _text(r), (
                "the link reached another object"
            )
        seen += 1
    assert seen > 8
    for finding_id in hostile.workbench.findings_by_id:
        r = _get(hostile, finding_path(finding_id))
        assert r.status == 200, finding_id


def test_finding_id_with_a_literal_percent_escape_round_trips(hostile: App) -> None:
    (drift,) = [i for i in hostile.workbench.findings_by_id if "foo%20bar" in i]
    assert _get(hostile, finding_path(drift)).status == 200
    # The decoded spelling is a different id: it must not match.
    assert _get(hostile, "/finding/" + quote(drift.replace("%20", " "), safe="")).status == 404


# --- static ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "/static/../pyproject.toml",
        "/static/..%2Fpyproject.toml",
        "/static/%2E%2E%2F%2E%2E%2Fpyproject.toml",
        "/static/chart.umd.min.js",  # packaged, but not on the allow-list
        "/static/__init__.py",
        "/static/",
        "/static",
    ],
)
def test_static_serves_only_the_allow_list(twin: App, target: str) -> None:
    assert _get(twin, target).status == 404


def test_static_allow_listed_asset_is_the_packaged_file(twin: App) -> None:
    r = _get(twin, "/static/dagre.min.js")
    assert r.status == 200
    assert ("Content-Type", "text/javascript; charset=utf-8") in r.headers
    assert r.body == (resources.files("strata_lookml.assets.js") / "dagre.min.js").read_bytes()


# --- security headers, methods, Host ---------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "target", "host", "status"),
    [
        ("GET", "/", HOST, 302),
        ("GET", "/findings", HOST, 200),
        ("HEAD", "/overview", HOST, 200),
        ("GET", "/explore/orders", HOST, 300),
        ("GET", "/field/accounts", HOST, 400),
        ("GET", "/nowhere", HOST, 404),
        ("GET", "/static/dagre.min.js", HOST, 200),
        ("GET", "/api/index.json", HOST, 200),
        ("POST", "/findings", HOST, 405),
        ("GET", "/findings", "evil.example", 403),
        ("GET", "/findings", None, 403),
    ],
)
def test_security_headers_on_every_response(
    twin: App, method: str, target: str, host: str | None, status: int
) -> None:
    r = _get(twin, target, method, host)
    assert r.status == status
    headers = dict(r.headers)
    assert headers["Content-Security-Policy"] == CSP
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert set(SECURITY_HEADERS) <= set(r.headers)


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
def test_non_get_methods_are_405(twin: App, method: str) -> None:
    r = _get(twin, "/findings", method)
    assert r.status == 405
    assert ("Allow", "GET, HEAD") in r.headers


def test_foreign_host_is_refused_before_routing_and_never_sees_the_token(twin: App) -> None:
    for target in ("/findings", "/nowhere", "/static/dagre.min.js", "/"):
        for method in ("GET", "POST"):
            r = _get(twin, target, method, f"evil.example:{PORT}")
            assert r.status == 403
            assert TOKEN.encode() not in r.body
            assert r.headers[0] == ("Content-Type", "text/plain; charset=utf-8")


def test_tokens_are_per_process_random() -> None:
    assert new_token() != new_token()
    assert len(new_token()) >= 32


# --- over a real socket ----------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def live(twin: App) -> Iterator[int]:
    port = _free_port()
    app = App(twin.workbench, allowed_hosts(port), TOKEN, twin.staleness)
    httpd = http.server.HTTPServer(("127.0.0.1", port), make_handler(app))
    thread = threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    yield port
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _request(
    port: int, method: str, path: str, host: str | None
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    if host is not None:
        conn.putheader("Host", host)
    conn.endheaders()
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, dict(resp.getheaders()), body


@pytest.mark.parametrize(
    ("method", "path", "status"),
    [
        ("GET", "/findings", 200),
        ("GET", "/static/../pyproject.toml", 404),
        ("GET", "/../pyproject.toml", 404),
        ("POST", "/findings", 405),
        ("DELETE", "/findings", 405),
        ("FOO", "/findings", 405),  # unknown to http.server: still the app's 405
    ],
)
def test_live_server_routes_and_headers(live: int, method: str, path: str, status: int) -> None:
    got, headers, body = _request(live, method, path, f"127.0.0.1:{live}")
    assert got == status
    assert headers["Content-Security-Policy"] == CSP
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert b"[project]" not in body


@pytest.mark.parametrize(
    "host", ["evil.example", "127.0.0.1:1", "localhost.evil.com:{p}", "", None]
)
def test_live_server_refuses_foreign_hosts(live: int, host: str | None) -> None:
    for method in ("GET", "FOO"):
        got, headers, body = _request(
            live, method, "/findings", None if host is None else host.format(p=live)
        )
        assert got == 403
        assert headers["Content-Security-Policy"] == CSP
        assert TOKEN.encode() not in body


def test_live_server_head_has_no_body(live: int) -> None:
    got, headers, body = _request(live, "HEAD", "/findings", f"localhost:{live}")
    assert got == 200
    assert int(headers["Content-Length"]) > 0
    assert body == b""


def test_live_server_malformed_request_gets_a_bare_error(live: int) -> None:
    with socket.create_connection(("127.0.0.1", live), timeout=5) as s:
        headers = b"".join(b"X-%d: y\r\n" % i for i in range(101))  # over http.server's 100
        s.sendall(b"GET /findings HTTP/1.1\r\nHost: 127.0.0.1\r\n" + headers + b"\r\n")
        data = b""
        while chunk := s.recv(65536):
            data += chunk
    head, _, body = data.partition(b"\r\n\r\n")
    assert head.startswith(b"HTTP/1.0 431")
    assert b"Content-Security-Policy: " in head
    assert TOKEN.encode() not in body


# --- hostile fixture through every route -----------------------------------------------------


class _Markup(HTMLParser):
    """Collects every tag and attribute the browser would see."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.attrs: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        self.attrs.extend(attrs)

    handle_startendtag = handle_starttag


_SHELL_TAGS = {
    "html",
    "head",
    "meta",
    "title",
    "link",
    "style",
    "script",
    "body",
    "nav",
    "a",
    "main",
    "p",
    "h1",
    "h2",
    "dl",
    "dt",
    "dd",
    "ul",
    "li",
    "div",
    "span",
    "section",
    "form",
    "input",
    "button",
    "kbd",
    "code",
    "i",
    "b",
    "bdi",
    "dialog",
    # the shared detail frame (S6)
    "aside",
    "textarea",
    "pre",
    # /overview report (S7): structure, table and the server-built SVG bars
    "article",
    "strong",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "svg",
    "rect",
}
_SHELL_ATTRS = {
    "lang",
    "charset",
    "name",
    "content",
    "href",
    "rel",
    "src",
    "defer",
    "id",
    "role",
    "class",
    "title",
    "type",
    "value",
    "placeholder",
    "method",
    "action",
    "hidden",
    "disabled",
    "aria-label",
    "aria-current",
    "aria-disabled",
    # /overview inline SVG bars (S7)
    "width",
    "height",
    "viewbox",
    "x",
    "y",
    "rx",
    "aria-hidden",
    "focusable",
    # the detail frame (S6)
    "readonly",
}
# The only scripts a page may load: allow-listed /static/ files behind the CSP's
# script-src 'self', each at most once. Nothing else that opens a <script> may appear.
_SANCTIONED_SCRIPTS = (
    '<script src="/static/workbench.js" defer></script>',
    '<script src="/static/detail.js" defer></script>',
)


def _assert_inert(target: str, response: Response) -> None:
    body = _text(response)
    content_type = dict(response.headers)["Content-Type"]
    if content_type.startswith("application/json"):
        assert "<" not in body, target  # `>` alone cannot open markup
        json.loads(body)
        return
    stripped = body
    for script in _SANCTIONED_SCRIPTS:
        assert body.count(script) <= 1, (target, script)
        stripped = stripped.replace(script, "")
    for raw in ("<img", "<script", "</script>", "onerror=alert(1)>"):
        assert raw not in stripped, (target, raw)
    parser = _Markup()
    parser.feed(body)
    assert set(parser.tags) <= _SHELL_TAGS, (target, set(parser.tags) - _SHELL_TAGS)
    for name, value in parser.attrs:
        assert not name.startswith("on"), (target, name)
        # data-* attributes are inert text the page script reads with getAttribute.
        assert name in _SHELL_ATTRS or name.startswith("data-"), (target, name)
        if name in ("href", "src", "action", "data-href"):
            assert value is not None and value.startswith("/") and not value.startswith("//"), (
                target,
                value,
            )


def test_hostile_names_never_reach_a_response_as_markup(hostile: App) -> None:
    wb = hostile.workbench
    assert len(wb.records) >= 5, "the fixture must produce findings to render"
    assert any(HOSTILE in r["source_file"] for r in wb.records if r["source_file"])
    q = quote(HOSTILE + "</script>\"'%2F..", safe="")
    targets = [
        "/",
        "/findings",
        f"/findings?q={q}&category={q}&status={q}&page={q}",
        f"/findings?status=all&q={q}",
        "/overview",
        f"/graph?focus={q}&hops={q}",
        f"/search?q={q}",
        "/api/index.json",
        f"/explore/{q}",
        f"/view/{q}",
        f"/pdt/{q}",
        f"/table/{q}",
        f"/field/{q}",
        f"/field/{q}.{q}",
        f"/finding/{q}",
        f"/static/{q}",
        f"/{q}",
        "/explore/a%3C%2Fscript%3Eb",  # ambiguous across the two models: candidates page
    ]
    targets += [p for n in wb.graph.nodes.values() if (p := object_path(n.id))]
    targets += [finding_path(i) for i in wb.findings_by_id]
    statuses = set()
    for target in targets:
        for method in ("GET", "POST"):
            response = _get(hostile, target, method)
            statuses.add(response.status)
            _assert_inert(target, response)
    assert {200, 300, 302, 400, 404, 405} <= statuses


def test_the_inertness_check_catches_raw_markup() -> None:
    """Negative control for `_assert_inert`: an unescaped payload fails it."""
    page = f'<html><body><a href="/x">{HOSTILE}</a></body></html>'.encode()
    with pytest.raises(AssertionError):
        _assert_inert("/x", Response(200, (("Content-Type", "text/html"),), page))
    attr = b'<html><body><a href="javascript:alert(1)">x</a></body></html>'
    with pytest.raises(AssertionError):
        _assert_inert("/x", Response(200, (("Content-Type", "text/html"),), attr))
    # Only the exact sanctioned script tag passes: another src, or an inline script, fails.
    for script in (
        b'<script src="/static/other.js" defer></script>',
        b"<script>alert(1)</script>",
        b'<script src="/static/workbench.js"></script>',
    ):
        page = b"<html><head>" + script + b"</head><body></body></html>"
        with pytest.raises(AssertionError):
            _assert_inert("/x", Response(200, (("Content-Type", "text/html"),), page))


# --- cache and staleness ---------------------------------------------------------------------


def test_second_start_hits_the_ir_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    builds = []
    real = pipeline.build_graph

    def counting(*args, **kwargs):  # type: ignore[no-untyped-def]
        builds.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(pipeline, "build_graph", counting)
    first = _workbench(TWIN)
    second = _workbench(TWIN)
    assert len(builds) == 1, "the second start must load the cache, not rebuild"
    assert [dict(r) for r in first.records] == [dict(r) for r in second.records]


def test_staleness_rechecks_at_most_every_interval_and_sticks() -> None:
    now = [0.0]
    calls = []
    current = {"lookml": 1}

    def fingerprint() -> dict[str, int]:
        calls.append(now[0])
        return dict(current)

    staleness = Staleness({"lookml": 1}, fingerprint, interval=10.0, clock=lambda: now[0])
    assert staleness.stale() is False and calls == []
    current["lookml"] = 2
    now[0] = 9.9
    assert staleness.stale() is False and calls == [], "no re-check inside the interval"
    now[0] = 10.0
    assert staleness.stale() is True and calls == [10.0]
    current["lookml"] = 1
    now[0] = 30.0
    assert staleness.stale() is True, "stays stale until a restart"


def test_a_repo_edit_shows_the_stale_banner(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "m.model.lkml").write_text('connection: "c"\nexplore: e {}\n', encoding="utf-8")
    (repo / "e.view.lkml").write_text("view: e { dimension: a {} }\n", encoding="utf-8")
    wb = _workbench(repo)
    now = [0.0]
    app = App(
        wb, allowed_hosts(PORT), TOKEN, Staleness(wb.inputs, wb.fingerprint, clock=lambda: now[0])
    )
    assert 'class="stale"' not in _text(_get(app, "/findings"))
    (repo / "e.view.lkml").write_text(
        "view: e { dimension: a {} dimension: b {} }\n", encoding="utf-8"
    )
    now[0] = 11.0
    assert 'class="stale"' in _text(_get(app, "/findings"))


# --- CLI -------------------------------------------------------------------------------------


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str) -> tuple[object, dict]:
    """Invoke the CLI; serve_forever answers one probe of /findings instead of blocking."""
    seen: dict = {}

    def fake_serve(self: http.server.HTTPServer) -> None:
        bound = self.server_address[1]
        seen["bound"] = bound

        def probe() -> None:
            seen["status"], _, seen["body"] = _request(
                bound, "GET", "/findings", f"127.0.0.1:{bound}"
            )

        t = threading.Thread(target=probe)
        t.start()
        self.handle_request()
        t.join()

    monkeypatch.setattr(http.server.HTTPServer, "serve_forever", fake_serve)
    monkeypatch.chdir(tmp_path)
    port = _free_port()
    result = CliRunner().invoke(
        strata_cli, [*args, "--repo", str(TWIN), "--port", str(port), "--no-browser"]
    )
    return result, seen


@pytest.mark.parametrize("command", ["workbench", "dashboard"])
def test_workbench_command_and_dashboard_alias_serve_the_workbench(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, command: str
) -> None:
    result, seen = _run(monkeypatch, tmp_path, command)
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert seen["status"] == 200
    assert b'<meta name="strata-token"' in seen["body"]
    assert f"http://127.0.0.1:{seen['bound']}/findings" in result.output  # type: ignore[attr-defined]
    assert not (tmp_path / "output").exists(), "the workbench writes no artifacts"


def test_workbench_url_on_another_port_warns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    result, seen = _run(monkeypatch, tmp_path, "workbench", "--workbench-url", "http://127.0.0.1:1")
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert "names port 1, but the workbench is on" in result.output  # type: ignore[attr-defined]


def test_workbench_flags_are_refused_with_out(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        strata_cli,
        ["dashboard", "--repo", str(TWIN), "--out", str(tmp_path), "--baseline", "b.json"],
    )
    assert result.exit_code == 2
    assert "apply to the workbench, not --out" in result.output


def test_bad_baseline_is_a_usage_error(tmp_path: Path) -> None:
    bad = tmp_path / "b.json"
    bad.write_text("{}", encoding="utf-8")
    result = CliRunner().invoke(
        strata_cli, ["workbench", "--repo", str(TWIN), "--baseline", str(bad)]
    )
    assert result.exit_code == 2
    assert "not a version 1 Strata baseline" in result.output


def test_legacy_export_still_writes_the_dashboard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(http.server.HTTPServer, "serve_forever", lambda self: self.server_close())
    monkeypatch.chdir(tmp_path)  # the legacy export serves its directory by chdir
    monkeypatch.setattr(dash, "DEFAULT_PORT", _free_port())
    out = tmp_path / "out"
    result = CliRunner().invoke(
        strata_cli, ["dashboard", "--repo", str(TWIN), "--out", str(out), "--no-browser"]
    )
    assert result.exit_code == 0, result.output
    assert (out / "dashboard.html").is_file()


def test_workbench_url_resolves_through_the_shared_resolver(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STRATA_WORKBENCH_URL", "http://127.0.0.1:1")
    result, _ = _run(monkeypatch, tmp_path, "workbench")
    assert result.exit_code == 0, result.output  # type: ignore[attr-defined]
    assert "http://127.0.0.1:1 names port 1" in result.output  # type: ignore[attr-defined]


def test_invalid_workbench_url_is_refused(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        strata_cli, ["workbench", "--repo", str(TWIN), "--workbench-url", "ftp://x"]
    )
    assert result.exit_code == 1
    assert "invalid workbench URL from --workbench-url" in result.output
