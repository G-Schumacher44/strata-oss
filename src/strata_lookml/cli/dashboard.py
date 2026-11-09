"""Loopback binding for `strata workbench` (alias `strata dashboard`): the Host allow-list and
the exclusive bind with port fallback. The request handler is `workbench/server.py`; `--out`
writes a file instead (`workbench/export.py`) and serves nothing.
"""

from __future__ import annotations

import http.server
from collections.abc import Callable

from strata_lookml.errors import StrataError
from strata_lookml.loopback import ExclusiveHTTPServer, port_in_use

DEFAULT_PORT = 8765
# Tried in order when the default port is busy and `--port` was not passed.
FALLBACK_PORTS = range(8766, 8786)


def allowed_hosts(port: int) -> frozenset[str]:
    """Host header values accepted for a loopback server bound to ``port`` (lowercase)."""
    hosts = ("127.0.0.1", "localhost", "[::1]")
    permitted = {f"{h}:{port}" for h in hosts}
    if port == 80:  # browsers omit the default port from Host
        permitted.update(hosts)
    return frozenset(permitted)


def bind_server(
    port: int,
    explicit: bool,
    fallback_ports: range | None = None,
    *,
    handler_factory: Callable[[int], type[http.server.BaseHTTPRequestHandler]],
) -> ExclusiveHTTPServer:
    """Bind the loopback server, with the Host allow-list built from the port actually bound.

    ``handler_factory(port)`` builds the handler for the candidate port. An explicit ``--port``
    that is busy fails; the default port falls back through the range.
    """
    fallback = FALLBACK_PORTS if fallback_ports is None else fallback_ports
    candidates = [port] if explicit else [port, *fallback]
    for candidate in candidates:
        try:
            # Loopback only, by IP literal: "localhost" can resolve to other interfaces on some hosts.
            return ExclusiveHTTPServer(("127.0.0.1", candidate), handler_factory(candidate))
        except OSError as exc:
            if not port_in_use(exc):
                raise
    if explicit:
        raise StrataError(
            f"Port {port} is already in use.",
            hint="Pass a different --port, or omit --port to use the first free port from "
            f"{port} up.",
        )
    tried = f"{port} and {candidates[1]}-{candidates[-1]}" if len(candidates) > 1 else str(port)
    raise StrataError(
        f"No free port for the dashboard (tried {tried}).",
        hint="Free a port, or pass --port with one that is open.",
    )
