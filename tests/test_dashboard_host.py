"""strata workbench — the Host allow-list built for a bound port (DNS-rebinding guard).

The workbench's own Host checks (refused before routing, never shown the token) are in
test_workbench_server.py; this pins the allow-list itself.
"""

from __future__ import annotations

from strata_lookml.cli.dashboard import allowed_hosts


def test_loopback_forms_are_allowed_with_the_port() -> None:
    assert allowed_hosts(8765) == {"127.0.0.1:8765", "localhost:8765", "[::1]:8765"}


def test_portless_hosts_only_permitted_on_port_80() -> None:
    portless = {"127.0.0.1", "localhost", "[::1]"}
    assert portless <= allowed_hosts(80)
    assert "127.0.0.1:80" in allowed_hosts(80)
    assert not portless & allowed_hosts(8765)
