"""strata dashboard — Host header allowlist (DNS-rebinding guard)."""

from __future__ import annotations

import http.client
import http.server
import threading
from collections.abc import Iterator
from functools import partial
from pathlib import Path

import pytest

from strata_lookml.cli.dashboard import make_handler


@pytest.fixture
def server(tmp_path: Path) -> Iterator[int]:
    (tmp_path / "secret.json").write_text('{"k": "v"}')
    probe = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
    port = probe.server_address[1]
    probe.server_close()
    handler = partial(make_handler(port), directory=str(tmp_path))
    httpd = http.server.HTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield port
    httpd.shutdown()
    httpd.server_close()


def _get(port: int, host: str | None) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.putrequest("GET", "/secret.json", skip_host=True)
    if host is not None:
        conn.putheader("Host", host)
    conn.endheaders()
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, body


@pytest.mark.parametrize("form", ["127.0.0.1:{p}", "localhost:{p}", "[::1]:{p}", "LOCALHOST:{p}"])
def test_loopback_host_served(server: int, form: str) -> None:
    status, body = _get(server, form.format(p=server))
    assert status == 200
    assert b'"k"' in body


@pytest.mark.parametrize(
    "host",
    ["evil.example", "evil.example:{p}", "127.0.0.1:1", "127.0.0.1", "localhost.evil.com:{p}", ""],
)
def test_foreign_host_refused(server: int, host: str) -> None:
    status, body = _get(server, host.format(p=server))
    assert status == 403
    assert b'"k"' not in body


def test_missing_host_refused(server: int) -> None:
    status, body = _get(server, None)
    assert status == 403
    assert b'"k"' not in body
