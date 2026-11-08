"""strata dashboard — default-port fallback and explicit-port failure (D9)."""

from __future__ import annotations

import http.client
import http.server
import socket
import threading
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest
from click.testing import CliRunner

from strata_lookml.cli import dashboard as dash
from strata_lookml.cli.main import strata_cli

REPO = Path(__file__).parent / "lookml" / "gcs_analytics"


def _free_ports(n: int) -> list[int]:
    """n distinct high ports, held only briefly to learn their numbers."""
    socks = [socket.socket() for _ in range(n)]
    try:
        for s in socks:
            s.bind(("127.0.0.1", 0))
        return sorted(s.getsockname()[1] for s in socks)
    finally:
        for s in socks:
            s.close()


@pytest.fixture
def ports(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[int, range]]:
    """A private default port and fallback range on free high ports (never the real 8765)."""
    base = _free_ports(1)[0]
    fallback = range(base + 1, base + 4)
    monkeypatch.setattr(dash, "DEFAULT_PORT", base)
    monkeypatch.setattr(dash, "FALLBACK_PORTS", fallback)
    yield base, fallback


def _occupy(stack: ExitStack, *ports: int) -> None:
    for p in ports:
        s = socket.socket()
        s.bind(("127.0.0.1", p))
        s.listen()
        stack.callback(s.close)


def _run_dashboard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *extra: str):
    """Invoke the command; serve_forever answers two probe requests instead of blocking."""
    seen: dict[str, int] = {}

    def fake_serve(self: http.server.HTTPServer) -> None:
        bound = self.server_address[1]
        seen["bound"] = bound

        def probe(host: str, key: str) -> None:
            conn = http.client.HTTPConnection("127.0.0.1", bound, timeout=5)
            conn.putrequest("GET", "/dashboard.html", skip_host=True)
            conn.putheader("Host", host)
            conn.endheaders()
            seen[key] = conn.getresponse().status
            conn.close()

        threads = [
            threading.Thread(target=probe, args=(f"127.0.0.1:{bound}", "bound_host")),
            threading.Thread(target=probe, args=(f"127.0.0.1:{dash.DEFAULT_PORT}", "default_host")),
        ]
        for t in threads:
            t.start()
        self.handle_request()
        self.handle_request()
        for t in threads:
            t.join()
        self.server_close()

    monkeypatch.setattr(http.server.HTTPServer, "serve_forever", fake_serve)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        strata_cli,
        ["dashboard", "--repo", str(REPO), "--out", str(tmp_path / "out"), "--no-browser", *extra],
    )
    return result, seen


def test_busy_default_falls_back_and_allowlist_uses_bound_port(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ports: tuple[int, range]
) -> None:
    base, fallback = ports
    with ExitStack() as stack:
        _occupy(stack, base)
        result, seen = _run_dashboard(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    assert seen["bound"] == fallback[0]
    assert f"http://127.0.0.1:{fallback[0]}/dashboard.html" in result.output
    assert seen["bound_host"] == 200
    assert seen["default_host"] == 403  # allow-list follows the bound port, not the default


def test_free_default_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ports: tuple[int, range]
) -> None:
    base, _ = ports
    result, seen = _run_dashboard(tmp_path, monkeypatch)
    assert result.exit_code == 0, result.output
    assert seen["bound"] == base
    assert "is busy" not in result.output


def test_explicit_busy_port_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ports: tuple[int, range]
) -> None:
    base, fallback = ports
    with ExitStack() as stack:
        _occupy(stack, fallback[0])  # explicit port busy; the default is free and must not be used
        result, seen = _run_dashboard(tmp_path, monkeypatch, "--port", str(fallback[0]))
    assert result.exit_code == 1
    assert f"Port {fallback[0]} is already in use" in result.output
    assert "bound" not in seen


def test_explicit_port_equal_to_default_value_is_still_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ports: tuple[int, range]
) -> None:
    # Detection is by click's parameter source, not by comparing against the default value.
    base, _ = ports
    with ExitStack() as stack:
        _occupy(stack, base)
        result, _ = _run_dashboard(tmp_path, monkeypatch, "--port", str(base))
    assert result.exit_code == 1
    assert f"Port {base} is already in use" in result.output


def test_whole_range_busy_is_a_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ports: tuple[int, range]
) -> None:
    base, fallback = ports
    with ExitStack() as stack:
        _occupy(stack, base, *fallback)
        result, seen = _run_dashboard(tmp_path, monkeypatch)
    assert result.exit_code == 1
    assert "No free port" in result.output
    assert f"{fallback[0]}-{fallback[-1]}" in result.output
    assert "bound" not in seen


def test_dashboard_and_oauth_share_one_exclusive_server(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from strata_lookml.l1 import oauth
    from strata_lookml.loopback import ExclusiveHTTPServer

    assert oauth.ExclusiveHTTPServer is ExclusiveHTTPServer
    assert dash.ExclusiveHTTPServer is ExclusiveHTTPServer
    # Reuse is off wherever it would permit a double bind (Windows), so a busy port is detected.
    assert ExclusiveHTTPServer.allow_reuse_address == (os.name != "nt")


def test_bound_dashboard_port_cannot_be_bound_twice(ports: tuple[int, range]) -> None:
    from strata_lookml.errors import StrataError

    base, _ = ports
    first = dash.bind_server(base, explicit=True)
    try:
        with pytest.raises(StrataError, match="already in use"):
            dash.bind_server(base, explicit=True)
    finally:
        first.server_close()


def _windows_busy(monkeypatch: pytest.MonkeyPatch, busy: set[int]) -> None:
    """Make binding any port in `busy` fail the way an exclusive Windows listener does."""
    import errno
    import sys

    real = dash.ExclusiveHTTPServer

    def fake(addr: tuple[str, int], handler: type) -> http.server.HTTPServer:
        if addr[1] in busy:
            err = OSError(errno.EACCES, "Permission denied")
            err.winerror = 10013  # type: ignore[attr-defined]
            raise err
        return real(addr, handler)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(dash, "ExclusiveHTTPServer", fake)


def test_windows_wsaeacces_triggers_fallback(
    monkeypatch: pytest.MonkeyPatch, ports: tuple[int, range]
) -> None:
    base, fallback = ports
    _windows_busy(monkeypatch, {base})
    server = dash.bind_server(base, explicit=False)
    try:
        assert server.server_address[1] == fallback[0]
    finally:
        server.server_close()


def test_windows_wsaeacces_explicit_port_is_already_in_use(
    monkeypatch: pytest.MonkeyPatch, ports: tuple[int, range]
) -> None:
    from strata_lookml.errors import StrataError

    base, _ = ports
    _windows_busy(monkeypatch, {base})
    with pytest.raises(StrataError, match="already in use"):
        dash.bind_server(base, explicit=True)


def test_eacces_off_windows_is_not_a_busy_port(
    monkeypatch: pytest.MonkeyPatch, ports: tuple[int, range]
) -> None:
    import errno

    base, _ = ports
    monkeypatch.setattr(
        dash,
        "ExclusiveHTTPServer",
        lambda *a: (_ for _ in ()).throw(OSError(errno.EACCES, "denied")),
    )
    with pytest.raises(OSError):
        dash.bind_server(base, explicit=False)
