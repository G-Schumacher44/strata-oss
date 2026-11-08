"""OAuth 2.0 helpers for `strata auth login`: PKCE, `state`, and the loopback redirect receiver.

Grounded on Looker's OAuth guide (https://docs.cloud.google.com/looker/docs/api-cors), which
sends `state`, `code_challenge_method=S256` and `code_challenge` on `/auth` and redeems the code
with the matching `code_verifier`. PKCE follows RFC 7636 §4; the receiver follows RFC 8252 §7.3
(loopback interface redirection). Looker matches a redirect URI *exactly* against the URIs
registered on the OAuth client app, so the receiver listens on the fixed port named in the
configured redirect URI rather than an ephemeral one.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import http.server
import secrets
import time
import urllib.parse
from typing import Any

from strata_lookml.loopback import ExclusiveHTTPServer

# The IP literal only (RFC 8252 §8.3): "localhost" may resolve to ::1 first, and the browser's
# redirect would then never reach the IPv4 listener.
LOOPBACK_HOST = "127.0.0.1"


class OAuthCallbackError(RuntimeError):
    pass


class OAuthStateMismatch(OAuthCallbackError):
    """The redirect's `state` is missing or wrong: not our login's redirect."""


def new_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for the S256 method (RFC 7636 §4.1-4.2).

    The verifier is 64 random bytes as base64url — 86 characters, inside the 43-128 range.
    """
    verifier = secrets.token_urlsafe(64)
    return verifier, pkce_challenge(verifier)


def pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def new_state() -> str:
    return secrets.token_urlsafe(32)


def code_from_callback(query: str, expected_state: str) -> str:
    """Extract the authorization code from a redirect's query string after verifying `state`.

    `query` may be a full redirect URL or just its query string. Fails closed: a missing or
    mismatched `state`, an `error` response, or a missing `code` all raise.
    """
    if "?" in query:
        query = urllib.parse.urlsplit(query.strip()).query
    params = urllib.parse.parse_qs(query.strip().lstrip("?"))
    state = params.get("state", [""])[0]
    if not state or not hmac.compare_digest(state.encode(), expected_state.encode()):
        raise OAuthStateMismatch("OAuth state did not match; refusing the authorization code")
    if "error" in params:
        raise OAuthCallbackError(f"Looker returned an OAuth error: {params['error'][0]}")
    code = params.get("code", [""])[0]
    if not code:
        raise OAuthCallbackError("redirect carried no authorization code")
    return code


def loopback_address(redirect_uri: str) -> tuple[int, str]:
    """(port, path) for a loopback redirect URI; raises for anything the receiver can't serve."""
    parts = urllib.parse.urlsplit(redirect_uri)
    if parts.scheme != "http" or parts.hostname != LOOPBACK_HOST or parts.port is None:
        raise OAuthCallbackError(
            "the loopback receiver needs a redirect URI of the form "
            f"http://127.0.0.1:<port>/<path>; got {redirect_uri!r} (use --no-browser to paste "
            "the redirect URL instead)"
        )
    return parts.port, parts.path or "/"


class LoopbackReceiver:
    """One-shot HTTP listener on 127.0.0.1 that captures a single OAuth redirect.

    Bind happens in the constructor, so the port is held before the browser is sent to Looker.
    Request logging is suppressed so the code never reaches the terminal.
    """

    def __init__(self, redirect_uri: str, expected_state: str) -> None:
        port, path = loopback_address(redirect_uri)
        captured: dict[str, str] = {}

        class _Handler(http.server.BaseHTTPRequestHandler):
            # A local client that connects and never sends must not stall the login.
            timeout = 5

            def do_GET(self) -> None:
                parts = urllib.parse.urlsplit(self.path)
                if parts.path != path:
                    self.send_error(404)
                    return
                try:
                    captured["code"] = code_from_callback(parts.query, expected_state)
                except OAuthStateMismatch:
                    # A stray or forged request (wrong/missing state) does not end the login:
                    # refuse it and keep waiting for the real redirect.
                    self.send_error(400)
                    return
                except OAuthCallbackError as exc:
                    # Our own redirect, carrying an error (e.g. the user denied access).
                    captured["error"] = str(exc)
                    self.send_error(400)
                    return
                body = b"Strata received the Looker redirect. You can close this tab."
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self._captured = captured
        self._server = ExclusiveHTTPServer((LOOPBACK_HOST, port), _Handler)

    def wait(self, timeout: float = 300.0) -> str:
        deadline = time.monotonic() + timeout
        try:
            while "code" not in self._captured:
                if "error" in self._captured:
                    raise OAuthCallbackError(self._captured["error"])
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise OAuthCallbackError("timed out waiting for the Looker redirect")
                self._server.timeout = min(remaining, 1.0)
                self._server.handle_request()
        finally:
            self._server.server_close()
        return self._captured["code"]

    def close(self) -> None:
        self._server.server_close()
