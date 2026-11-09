"""The workbench's loopback HTTP adapter: `http.server` in, `App.respond` out.

A plain `BaseHTTPRequestHandler`: no `SimpleHTTPRequestHandler`, no working-directory change,
no filesystem path ever built from a request. Binding (loopback IP, port fallback, exclusive
bind, the Host allow-list for the bound port) is `cli.dashboard.bind_server`, shared with the
legacy export server.
"""

from __future__ import annotations

import http.server
import secrets
import sys
import traceback
from http import HTTPStatus
from typing import Any

from strata_lookml.workbench.app import App, Response, bare_error


def new_token() -> str:
    """The per-process token pages expose in `<meta name="strata-token">` (checked by the
    triage POST once it lands)."""
    return secrets.token_urlsafe(32)


def make_handler(app: App) -> type[http.server.BaseHTTPRequestHandler]:
    """The request handler for one bound server; `app` already holds that port's Host allow-list."""

    class WorkbenchHandler(http.server.BaseHTTPRequestHandler):
        def version_string(self) -> str:
            return "strata-workbench"

        def log_message(self, format: str, *args: Any) -> None:
            pass

        def do_GET(self) -> None:
            self._dispatch()

        def do_HEAD(self) -> None:
            self._dispatch()

        def send_error(
            self, code: int, message: str | None = None, explain: str | None = None
        ) -> None:
            # An unknown method arrives here as 501 before any do_* runs: answer it through
            # the app (Host check, then 405) like every other request.
            if code == HTTPStatus.NOT_IMPLEMENTED and self.command:
                self._dispatch()
                return
            # Malformed request line or headers: the Host is unknown, so no page.
            self.close_connection = True
            self._send(bare_error(code))

        def _dispatch(self) -> None:
            if self.command not in ("GET", "HEAD"):
                # The body (if any) is never read; do not let it parse as a next request.
                self.close_connection = True
            try:
                response = app.respond(self.command, self.path, self.headers.get("Host"))
            except Exception:  # an unanticipated bug: report it, never leak it to the page
                traceback.print_exc(file=sys.stderr)
                response = bare_error(HTTPStatus.INTERNAL_SERVER_ERROR)
            self._send(response)

        def _send(self, response: Response) -> None:
            self.send_response(response.status)
            for name, value in response.headers:
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(response.body)

    return WorkbenchHandler
