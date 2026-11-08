"""Loopback HTTP server that never shares a port that is already in use."""

from __future__ import annotations

import errno
import http.server
import os
import socket
import sys


class ExclusiveHTTPServer(http.server.HTTPServer):
    """HTTPServer whose bind fails (EADDRINUSE) when another socket holds the address.

    POSIX: SO_REUSEADDR only lets a retry rebind while the last connection sits in TIME_WAIT; it
    never lets a second socket bind an address that is actively listening.
    Windows: SO_REUSEADDR *would* allow that, so it is off and the bind is exclusive instead.
    """

    allow_reuse_address = os.name != "nt"

    def server_bind(self) -> None:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows only
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def port_in_use(exc: OSError) -> bool:
    """True when a bind failed because another socket holds the port.

    Windows reports an exclusive listener on the same port as WSAEACCES (10013), not EADDRINUSE.
    """
    if exc.errno == errno.EADDRINUSE:
        return True
    return sys.platform == "win32" and (
        exc.errno == errno.EACCES or getattr(exc, "winerror", None) == 10013
    )
