"""POST /api/triage (workbench S9): the one write, refused unless a page of this server sent it.

Every refusal is checked three ways: the status, that no `TriageStore` method ran (a spy on
the class), and that the store file on disk is byte-identical afterwards.
"""

from __future__ import annotations

import http.client
import http.server
import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest

from strata_lookml.cli.dashboard import allowed_hosts
from strata_lookml.pipeline import build_graph
from strata_lookml.triage import TriageStore
from strata_lookml.workbench import server as server_mod
from strata_lookml.workbench.app import MAX_TRIAGE_BODY, SECURITY_HEADERS, App, Response
from strata_lookml.workbench.index import Staleness, Workbench, index_graph
from strata_lookml.workbench.server import make_handler

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "lookml" / "enterprise_mono"
USAGE = ROOT / "fixtures" / "enterprise_usage_facts.json"
SCHEMA = ROOT / "fixtures" / "enterprise_schema_facts.json"
PORT = 18766  # only ever a Host string for App-level tests, never bound
HOST = f"127.0.0.1:{PORT}"
TOKEN = "test-token-not-secret"


@pytest.fixture(autouse=True)
def _home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """The triage store and IR cache live under ~/.strata: keep them in a temp HOME."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("STRATA_CACHE_PATH", raising=False)


@pytest.fixture(scope="module")
def wb() -> Workbench:
    graph = build_graph(REPO, USAGE, SCHEMA)
    return index_graph(
        graph,
        repo=REPO,
        usage_fixture=str(USAGE),
        schema_fixture=str(SCHEMA),
        inputs={},
    )


def _ids(wb: Workbench, n: int) -> list[str]:
    return list(wb.findings_by_id)[:n]


def _app(wb: Workbench, port: int = PORT) -> App:
    return App(wb, allowed_hosts(port), TOKEN, Staleness(wb.inputs, wb.fingerprint))


def _headers(body: bytes, host: str = HOST, **override: str | None) -> list[tuple[str, str]]:
    """What workbench.js sends; `override` replaces (or, with None, drops) a header."""
    base: dict[str, str | None] = {
        "Host": host,
        "Origin": f"http://{host}",
        "Sec-Fetch-Site": "same-origin",
        "Content-Type": "application/json",
        "X-Strata-Token": TOKEN,
        "Content-Length": str(len(body)),
    }
    for name, value in override.items():
        base[name.replace("_", "-")] = value
    return [(k, v) for k, v in base.items() if v is not None]


def _body(payload: Any) -> bytes:
    return json.dumps(payload).encode()


class _Reader:
    """A body reader that records whether the app read the body at all."""

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.reads: list[int] = []

    def __call__(self, n: int) -> bytes:
        self.reads.append(n)
        return self.body[:n]


def _post(
    app: App,
    body: bytes,
    headers: list[tuple[str, str]] | None = None,
    method: str = "POST",
    reader: _Reader | None = None,
) -> Response:
    headers = _headers(body) if headers is None else headers
    host = next((v for k, v in headers if k.lower() == "host"), None)
    return app.respond(method, "/api/triage", host, headers, reader or _Reader(body))


def _json(response: Response) -> Any:
    assert dict(response.headers)["Content-Type"] == "application/json; charset=utf-8"
    return json.loads(response.body)


@pytest.fixture
def spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every TriageStore method call from here on, by name."""
    calls: list[str] = []
    for name in ("acknowledge", "unacknowledge", "observe", "snapshot", "_mutate"):
        original: Callable[..., Any] = getattr(TriageStore, name)

        def wrapper(
            self: TriageStore, *a: Any, _o: Any = original, _n: str = name, **k: Any
        ) -> Any:
            calls.append(_n)
            return _o(self, *a, **k)

        monkeypatch.setattr(TriageStore, name, wrapper)
    return calls


@pytest.fixture
def seeded(wb: Workbench) -> tuple[App, Path, bytes]:
    """An app whose store file already exists (one id acked), and that file's bytes."""
    store = TriageStore.open(REPO, wb.graph)
    store.acknowledge([_ids(wb, 2)[1]], "seed")
    return _app(wb), store.path, store.path.read_bytes()


# --- refusals: the store is never called --------------------------------------------------

_GOOD = _body({"action": "ack", "ids": ["placeholder"]})
_OTHER = "evil.example"


def _refusal_cases() -> list[Any]:
    def h(**kw: str | None) -> list[tuple[str, str]]:
        return _headers(_GOOD, **kw)

    cases: list[tuple[str, list[tuple[str, str]], bytes, int]] = [
        ("origin missing", h(Origin=None), _GOOD, 403),
        ("origin other host", h(Origin=f"http://{_OTHER}"), _GOOD, 403),
        ("origin other port", h(Origin="http://127.0.0.1:1"), _GOOD, 403),
        ("origin other allowed host", h(Origin=f"http://localhost:{PORT}"), _GOOD, 403),
        ("origin null", h(Origin="null"), _GOOD, 403),
        ("origin https", h(Origin=f"https://{HOST}"), _GOOD, 403),
        ("origin twice", h() + [("Origin", f"http://{HOST}")], _GOOD, 400),
        ("fetch-site cross-site", h(Sec_Fetch_Site="cross-site"), _GOOD, 403),
        ("fetch-site same-site", h(Sec_Fetch_Site="same-site"), _GOOD, 403),
        ("fetch-site none", h(Sec_Fetch_Site="none"), _GOOD, 403),
        ("type text/plain", h(Content_Type="text/plain"), _GOOD, 415),
        ("type form", h(Content_Type="application/x-www-form-urlencoded"), _GOOD, 415),
        ("type multipart", h(Content_Type="multipart/form-data; boundary=x"), _GOOD, 415),
        ("type json+charset", h(Content_Type="application/json; charset=utf-8"), _GOOD, 415),
        ("type missing", h(Content_Type=None), _GOOD, 415),
        ("token missing", h(X_Strata_Token=None), _GOOD, 403),
        ("token wrong", h(X_Strata_Token=TOKEN + "x"), _GOOD, 403),
        ("token non-ascii", h(X_Strata_Token="tök"), _GOOD, 403),
        ("foreign host", _headers(_GOOD, host=f"{_OTHER}:{PORT}"), _GOOD, 403),
        ("length missing", h(Content_Length=None), _GOOD, 411),
        ("chunked", h(Transfer_Encoding="chunked"), _GOOD, 411),
        ("length not a number", h(Content_Length="12a"), _GOOD, 400),
        ("length negative", h(Content_Length="-1"), _GOOD, 400),
        ("body short of length", h(Content_Length=str(len(_GOOD) + 5)), _GOOD, 400),
        ("malformed json", _headers(b"{nope"), b"{nope", 400),
        ("not utf-8", _headers(b"\xff\xfe"), b"\xff\xfe", 400),
    ]
    oversize = b" " * (MAX_TRIAGE_BODY + 1)
    cases.append(("oversize", _headers(oversize), oversize, 413))
    for name, payload in [
        ("json list", ["ack"]),
        ("action missing", {"ids": ["x"]}),
        ("action unknown", {"action": "delete", "ids": ["x"]}),
        ("ids empty", {"action": "ack", "ids": []}),
        ("ids a string", {"action": "ack", "ids": "x"}),
        ("ids not strings", {"action": "ack", "ids": [1]}),
        ("id empty", {"action": "ack", "ids": [""]}),
        ("note on unack", {"action": "unack", "ids": ["x"], "note": "n"}),
        ("note not a string", {"action": "ack", "ids": ["x"], "note": 3}),
        ("extra key", {"action": "ack", "ids": ["x"], "path": "/etc"}),
    ]:
        b = _body(payload)
        cases.append((name, _headers(b), b, 400))
    return [pytest.param(hd, b, st, id=name) for name, hd, b, st in cases]


@pytest.mark.parametrize(("headers", "body", "status"), _refusal_cases())
def test_refused_requests_never_reach_the_store(
    seeded: tuple[App, Path, bytes],
    spy: list[str],
    headers: list[tuple[str, str]],
    body: bytes,
    status: int,
) -> None:
    app, path, before = seeded
    reader = _Reader(body)
    r = _post(app, body, headers, reader=reader)
    assert r.status == status
    assert spy == []
    assert path.read_bytes() == before
    assert set(SECURITY_HEADERS) <= set(r.headers)
    assert not [k for k, _ in r.headers if k.lower().startswith("access-control")]
    assert TOKEN.encode() not in r.body
    if status != 400:  # every header check runs before the body is read
        assert reader.reads == []
    if dict(headers).get("Host") == HOST:  # a refused Host gets the bare plain-text 403
        assert set(_json(r)) == {"error", "code", "hint"}


def test_the_refusal_cases_cover_every_check() -> None:
    """Each documented check has at least one case (a check without one could be deleted)."""
    names = {p.id for p in _refusal_cases()}
    for prefix in ("origin", "fetch-site", "type", "token", "foreign host", "length", "oversize"):
        assert any(n.startswith(prefix) for n in names), prefix


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS", "PUT", "DELETE"])
def test_other_methods_on_the_endpoint_are_405_without_cors(
    seeded: tuple[App, Path, bytes], spy: list[str], method: str
) -> None:
    app, path, before = seeded
    r = _post(app, _GOOD, method=method)
    assert r.status == 405
    assert ("Allow", "POST") in r.headers
    assert not [k for k, _ in r.headers if k.lower().startswith("access-control")]
    assert spy == [] and path.read_bytes() == before


def test_post_elsewhere_is_still_405_get_only(seeded: tuple[App, Path, bytes]) -> None:
    app, _, _ = seeded
    body = _body({"action": "ack", "ids": ["x"]})
    r = app.respond("POST", "/findings", HOST, _headers(body), _Reader(body))
    assert r.status == 405 and ("Allow", "GET, HEAD") in r.headers


def test_unknown_id_is_400_and_writes_nothing(
    wb: Workbench, seeded: tuple[App, Path, bytes]
) -> None:
    app, path, before = seeded
    good = _ids(wb, 1)[0]
    body = _body({"action": "ack", "ids": [good, "dead:view:<not-a-finding>"]})
    r = _post(app, body)
    assert r.status == 400
    error = _json(r)
    assert error["code"] == "invalid_input" and error["hint"]
    assert "<" not in r.body.decode()  # an echoed id stays inert JSON
    assert path.read_bytes() == before


def test_concurrency_exhaustion_is_409(
    wb: Workbench, seeded: tuple[App, Path, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    app, path, before = seeded
    monkeypatch.setattr(TriageStore, "_replace", lambda self, document, base_rev: False)
    monkeypatch.setattr("strata_lookml.triage._BACKOFF_S", 0)
    r = _post(app, _body({"action": "ack", "ids": _ids(wb, 1)}))
    assert r.status == 409
    assert _json(r)["hint"] == "retry"
    assert path.read_bytes() == before


# --- the write lands -------------------------------------------------------------------------


class _StatusCells(HTMLParser):
    """Each Findings row's ids and the class of its status cell."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[list[str], str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if "data-row" in a:
            self.rows.append((json.loads(a["data-ids"] or "[]"), ""))
        elif "data-status" in a and self.rows:
            ids, _ = self.rows[-1]
            self.rows[-1] = (ids, a.get("class") or "")


def _status_on_findings(app: App, finding_id: str) -> str:
    page = app.respond("GET", "/findings?status=all", HOST)
    parser = _StatusCells()
    parser.feed(page.body.decode())
    (cls,) = [c for ids, c in parser.rows if finding_id in ids]
    return cls


def test_ack_then_unack_round_trips_through_the_store(wb: Workbench) -> None:
    app = _app(wb)
    fid = _ids(wb, 1)[0]
    assert _status_on_findings(app, fid) == "st st-new"

    r = _post(app, _body({"action": "ack", "ids": [fid], "note": "<b>kept</b>"}))
    assert r.status == 200
    data = _json(r)
    assert [row["id"] for row in data["rows"]] == [fid] and data["untracked"] == []
    (row,) = data["rows"]
    assert (row["status"], row["label"], row["note"]) == ("acknowledged", "ack", "<b>kept</b>")
    assert "<" not in r.body.decode()
    stored = TriageStore.open(REPO, wb.graph).snapshot()["ids"][fid]
    assert stored["note"] == "<b>kept</b>" and "unacked_at" not in stored
    assert _status_on_findings(app, fid) == "st st-acknowledged"

    r = _post(app, _body({"action": "unack", "ids": [fid]}))
    assert r.status == 200
    assert _json(r)["rows"][0]["status"] == "new"
    assert "unacked_at" in TriageStore.open(REPO, wb.graph).snapshot()["ids"][fid]
    assert _status_on_findings(app, fid) == "st st-new"


def test_unack_of_an_id_never_acked_is_400(wb: Workbench) -> None:
    r = _post(_app(wb), _body({"action": "unack", "ids": _ids(wb, 1)}))
    assert r.status == 400 and _json(r)["code"] == "invalid_input"
    assert not TriageStore.open(REPO, wb.graph).path.exists()


# --- over a real socket ---------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture
def live(wb: Workbench) -> Iterator[int]:
    port = _free_port()
    httpd = http.server.HTTPServer(("127.0.0.1", port), make_handler(_app(wb, port)))
    thread = threading.Thread(target=httpd.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    yield port
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def _send(
    port: int, body: bytes, headers: list[tuple[str, str]]
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.putrequest("POST", "/api/triage", skip_host=True, skip_accept_encoding=True)
    for name, value in headers:
        conn.putheader(name, value)
    conn.endheaders()
    conn.send(body)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    return resp.status, dict(resp.getheaders()), data


def _live_ack(port: int, ids: list[str]) -> tuple[int, dict[str, str], bytes]:
    body = _body({"action": "ack", "ids": ids})
    return _send(port, body, _headers(body, host=f"127.0.0.1:{port}"))


def test_live_ack_and_refusals(live: int, wb: Workbench) -> None:
    fid = _ids(wb, 1)[0]
    body = _body({"action": "ack", "ids": [fid]})
    good = _headers(body, host=f"127.0.0.1:{live}")
    no_origin = [(k, v) for k, v in good if k != "Origin"]
    status, headers, _ = _send(live, body, no_origin)
    assert status == 403 and headers["Content-Security-Policy"]
    assert not TriageStore.open(REPO, wb.graph).path.exists()
    status, _, data = _live_ack(live, [fid])
    assert status == 200, data
    assert TriageStore.open(REPO, wb.graph).snapshot()["ids"][fid]["acked_at"]


def test_a_stalled_body_times_out_and_the_server_keeps_serving(
    live: int, wb: Workbench, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(server_mod, "BODY_TIMEOUT_S", 0.3)
    host = f"127.0.0.1:{live}"
    body = _body({"action": "ack", "ids": _ids(wb, 1)})
    head = "".join(f"{k}: {v}\r\n" for k, v in _headers(body + b"   ", host=host))
    with socket.create_connection(("127.0.0.1", live), timeout=5) as s:
        s.sendall(f"POST /api/triage HTTP/1.1\r\n{head}\r\n".encode() + body)  # 3 bytes short
        data = b""
        while chunk := s.recv(65536):
            data += chunk
    assert data.startswith(b"HTTP/1.0 400")
    assert not TriageStore.open(REPO, wb.graph).path.exists()
    status, _, _ = _live_ack(live, _ids(wb, 1))
    assert status == 200


def test_cli_and_web_acks_made_at_once_both_land(live: int, wb: Workbench) -> None:
    """`strata ack` in another process while the page posts: no write is lost."""
    cli_id, *web_ids = _ids(wb, 4)
    strata = Path(sys.executable).with_name("strata")
    proc = subprocess.Popen(
        [str(strata), "ack", "--repo", str(REPO), "--usage-fixture", str(USAGE)]
        + ["--schema-fixture", str(SCHEMA), cli_id],
        env={**os.environ},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    posts = 0
    while proc.poll() is None:
        status, _, data = _live_ack(live, [web_ids[posts % len(web_ids)]])
        assert status == 200, data
        posts += 1
        time.sleep(0.01)
    out, err = proc.communicate()
    assert proc.returncode == 0, err.decode()
    assert posts >= len(web_ids), "the web side must write while the CLI runs"
    stored = TriageStore.open(REPO, wb.graph).snapshot()["ids"]
    for fid in (cli_id, *web_ids):
        assert fid in stored and "unacked_at" not in stored[fid], fid


# --- GET /api/pr-comment: the other API route stays read-only and same-origin -----------------


def test_pr_comment_route_is_read_only_host_checked_and_never_cors_readable(wb: Workbench) -> None:
    """A cross-origin page may fire the GET but cannot read the answer: no CORS header is ever
    sent. Unknown ids are 404 without echoing the request."""
    app = _app(wb)
    fid = _ids(wb, 1)[0]
    hostile = "<script>alert(1)</script>"
    cross = [("Origin", "http://evil.example"), ("Sec-Fetch-Site", "cross-site")]
    ok = app.respond("GET", f"/api/pr-comment?id={fid}", HOST, cross)
    assert ok.status == 200
    headers = dict(ok.headers)
    assert headers["Content-Type"] == "text/plain; charset=utf-8"
    assert headers["X-Content-Type-Options"] == "nosniff"
    for method in ("GET", "HEAD", "POST", "OPTIONS", "PUT"):
        for target in (f"/api/pr-comment?id={fid}", "/api/pr-comment?id=" + hostile):
            r = app.respond(method, target, HOST, cross)
            assert not [k for k, _ in r.headers if k.lower().startswith("access-control")]
            if method not in ("GET", "HEAD"):
                assert r.status == 405 and ("Allow", "GET, HEAD") in r.headers
    missing = app.respond("GET", "/api/pr-comment?id=" + hostile, HOST)
    assert missing.status == 404
    assert b"<script>alert" not in missing.body and b"alert(1)" not in missing.body
    foreign = app.respond("GET", f"/api/pr-comment?id={fid}", f"evil.example:{PORT}")
    assert foreign.status == 403 and foreign.body == b"403 Forbidden\n"
