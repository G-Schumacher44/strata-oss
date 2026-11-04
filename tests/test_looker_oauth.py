"""Looker OAuth + token storage invariants: PKCE, state, loopback capture, token binding."""

from __future__ import annotations

import http.server
import json
import os
import socket
import stat
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
from click.testing import CliRunner

from strata_lookml.l1 import looker
from strata_lookml.l1.looker import (
    LiveLookerNotConfigured,
    LookerAPIError,
    LookerQueryRunner,
    LookerSystemActivityProvider,
    LookerToken,
    auth_url,
    exchange_code,
    load_token,
    save_token,
)
from strata_lookml.l1.oauth import (
    LoopbackReceiver,
    OAuthCallbackError,
    code_from_callback,
    new_pkce_pair,
    pkce_challenge,
)

posix_only = pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- PKCE + auth URL ---


def test_pkce_matches_rfc7636_appendix_b_vector():
    assert (
        pkce_challenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )
    verifier, challenge = new_pkce_pair()
    assert 43 <= len(verifier) <= 128
    assert challenge == pkce_challenge(verifier) and "=" not in challenge


def test_auth_url_carries_documented_params():
    url = auth_url("https://example.looker.com/", state="st", code_challenge="ch")
    parts = urllib.parse.urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://example.looker.com/auth"
    assert urllib.parse.parse_qs(parts.query) == {
        "response_type": ["code"],
        "client_id": [looker.DEFAULT_CLIENT_ID],
        "redirect_uri": [looker.DEFAULT_REDIRECT_URI],
        "scope": ["cors_api"],
        "state": ["st"],
        "code_challenge_method": ["S256"],
        "code_challenge": ["ch"],
    }
    assert ":8765" not in looker.DEFAULT_REDIRECT_URI  # never the dashboard's port


def test_exchange_code_posts_json_to_api_token(monkeypatch):
    seen = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            body = {"access_token": "tok_abcdefghijklmnop", "expires_in": 3600}
            return json.dumps({**body, "refresh_token": "r"}).encode()

    def fake_open(request, timeout):
        seen["url"] = request.full_url
        seen["ctype"] = request.get_header("Content-type")
        seen["auth"] = request.get_header("Authorization")
        seen["body"] = json.loads(request.data)
        return _Resp()

    monkeypatch.setattr(looker._OPENER, "open", fake_open)
    token = exchange_code("https://api.example.com:19999/", "the-code", "the-verifier")

    assert seen["url"] == "https://api.example.com:19999/api/token"
    assert seen["ctype"] == "application/json;charset=UTF-8"
    assert seen["auth"] is None
    assert seen["body"] == {
        "grant_type": "authorization_code",
        "client_id": looker.DEFAULT_CLIENT_ID,
        "redirect_uri": looker.DEFAULT_REDIRECT_URI,
        "code": "the-code",
        "code_verifier": "the-verifier",
    }
    assert token.looker_url == "https://api.example.com:19999"
    assert "refresh_token" not in vars(token)  # undocumented refresh -> not persisted


# --- state + loopback receiver ---


def test_callback_state_is_verified():
    assert code_from_callback("http://127.0.0.1:1/cb?code=abc&state=s1", "s1") == "abc"
    with pytest.raises(OAuthCallbackError, match="state"):
        code_from_callback("http://127.0.0.1:1/cb?code=abc&state=forged", "s1")
    with pytest.raises(OAuthCallbackError, match="state"):
        code_from_callback("code=abc", "s1")


def test_loopback_receiver_captures_one_redirect():
    port = _free_port()
    receiver = LoopbackReceiver(f"http://127.0.0.1:{port}/oauth/callback")
    replies = []

    def browser():
        base = f"http://127.0.0.1:{port}"
        try:
            urllib.request.urlopen(f"{base}/other?code=x&state=s", timeout=5)
        except urllib.error.HTTPError as exc:
            replies.append(exc.code)
        with urllib.request.urlopen(f"{base}/oauth/callback?code=c0de&state=s", timeout=5) as r:
            replies.append(r.status)

    t = threading.Thread(target=browser)
    t.start()
    assert receiver.wait("s", timeout=10) == "c0de"
    t.join()
    assert replies == [404, 200]


def test_loopback_receiver_refuses_non_loopback_redirect():
    with pytest.raises(OAuthCallbackError, match="loopback"):
        LoopbackReceiver("https://app.example.com/callback")


def test_login_no_browser_reads_redirect_from_stdin(tmp_path, monkeypatch):
    import strata_lookml.cli.auth as auth_cli

    monkeypatch.setattr(auth_cli, "new_state", lambda: "fixed-state")
    got = {}

    def fake_exchange(api_url, code, verifier, client_id, redirect_uri):
        got.update(api_url=api_url, code=code, verifier=verifier)
        return LookerToken(access_token="tok_abcdefghijklmnop", looker_url=api_url)

    monkeypatch.setattr(auth_cli, "exchange_code", fake_exchange)
    path = tmp_path / "t" / "tokens.json"
    args = ["login", "--looker-url", "https://x.looker.com", "--no-browser"]
    args += ["--token-path", str(path)]

    forged = CliRunner().invoke(auth_cli.auth, args, input="http://h/cb?code=c&state=bad\n")
    assert forged.exit_code != 0 and not path.exists() and not got

    ok = CliRunner().invoke(auth_cli.auth, args, input="http://h/cb?code=c&state=fixed-state\n")
    assert ok.exit_code == 0, ok.output
    assert got["code"] == "c" and got["api_url"] == "https://x.looker.com"
    assert "tok_abcdefghijklmnop" not in ok.output
    assert load_token(path).access_token == "tok_abcdefghijklmnop"


# --- token binding, expiry, redirects ---


def _token(url: str = "https://corp.looker.com", **kw) -> LookerToken:
    return LookerToken(access_token="tok_abcdefghijklmnop", looker_url=url, **kw)


def test_token_is_never_sent_to_another_origin(tmp_path):
    with pytest.raises(LiveLookerNotConfigured, match="refusing to send"):
        LookerQueryRunner("https://evil.example.com", _token())
    with pytest.raises(LiveLookerNotConfigured, match="refusing to send"):
        LookerQueryRunner("https://corp.looker.com:8443", _token())
    path = tmp_path / "tokens.json"
    save_token(_token(), path)
    with pytest.raises(LiveLookerNotConfigured, match="refusing to send"):
        LookerSystemActivityProvider.from_config("https://evil.example.com", token_path=path)
    assert LookerSystemActivityProvider.from_config(None, token_path=path).runner.token


def test_expired_token_is_refused():
    with pytest.raises(LiveLookerNotConfigured, match="expired"):
        LookerQueryRunner("https://corp.looker.com", _token(expires_at=time.time() - 1))


class _Recorder(http.server.BaseHTTPRequestHandler):
    hits: list[str] = []
    location = ""

    def do_POST(self):
        type(self).hits.append(self.headers.get("Authorization", ""))
        if type(self).location:
            self.send_response(302)
            self.send_header("Location", type(self).location)
        else:
            self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = do_POST

    def log_message(self, *a):
        pass


def test_redirect_never_carries_the_token_elsewhere():
    class Origin(_Recorder):
        hits: list[str] = []

    class Elsewhere(_Recorder):
        hits: list[str] = []

    other = http.server.HTTPServer(("127.0.0.1", 0), Elsewhere)
    origin = http.server.HTTPServer(("127.0.0.1", 0), Origin)
    Origin.location = f"http://127.0.0.1:{other.server_port}/steal"
    for srv in (origin, other):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{origin.server_port}"
        with pytest.raises(LookerAPIError, match="HTTP 302"):
            LookerQueryRunner(base, _token(base)).post_json("/api/4.0/x", {})
        assert Origin.hits == ["Bearer tok_abcdefghijklmnop"]
        assert Elsewhere.hits == []
    finally:
        origin.shutdown()
        other.shutdown()


# --- storage ---


@posix_only
def test_save_token_is_0600_in_0700_dir(tmp_path):
    folder = tmp_path / "strata"
    folder.mkdir(mode=0o755)
    os.chmod(folder, 0o755)
    path = folder / "tokens.json"
    save_token(_token(), path)
    save_token(_token(), path)  # overwrite path: still atomic, still tight
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert [p.name for p in folder.iterdir()] == ["tokens.json"]  # no temp left behind


@posix_only
def test_load_token_refuses_group_or_world_access(tmp_path):
    path = tmp_path / "tokens.json"
    save_token(_token(), path)
    os.chmod(path, 0o640)
    with pytest.raises(LiveLookerNotConfigured, match="chmod 600"):
        load_token(path)


def test_legacy_token_without_origin_is_refused(tmp_path):
    path = Path(tmp_path) / "tokens.json"
    path.write_text(json.dumps({"access_token": "x" * 20}), encoding="utf-8")
    os.chmod(path, 0o600)
    with pytest.raises(LiveLookerNotConfigured, match="looker_url"):
        load_token(path)
