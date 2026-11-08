"""Read-only Looker/System Activity provider for live L1 enrichment.

OAuth follows Looker's guide at https://docs.cloud.google.com/looker/docs/api-cors: the browser
goes to `/auth` on the Looker UI host; the code is redeemed with a JSON POST to `/api/token` on
the Looker API host ("The `/token` endpoint exists only on the Looker API host, and the `/auth`
endpoint exists only on the Looker UI host."). Not yet validated against a live instance.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from strata_lookml.config import ensure_private_dir
from strata_lookml.l1.replay import _latest_iso
from strata_lookml.l1.types import ContentReference, ExploreUsage, PDTBuild

# The `client_guid` the OAuth client app is registered under; sent as `client_id` in the flow.
DEFAULT_CLIENT_ID = "com.gsanalytics.strata.cli"
# Loopback redirect (RFC 8252 §7.3). Looker matches redirect URIs exactly against the ones
# registered on the client app, so the port is fixed; it is deliberately not the dashboard's 8765.
DEFAULT_REDIRECT_URI = "http://127.0.0.1:48765/oauth/callback"
DEFAULT_TOKEN_PATH = Path.home() / ".strata" / "tokens.json"
API_VERSION = "4.0"
OAUTH_SCOPE = "cors_api"
# Treat a token this close to expiry as expired, so a request never starts with a dying token.
EXPIRY_SKEW_SECONDS = 30


class LookerUsageAdapter(Protocol):
    """Adapter interface; implementations must be read-only."""

    def explore_usage(self) -> list[ExploreUsage]: ...

    def content_references(self) -> list[ContentReference]: ...

    def pdt_builds(self) -> list[PDTBuild]: ...


class LiveLookerNotConfigured(RuntimeError):
    pass


class LookerAPIError(RuntimeError):
    pass


class DisabledLookerAdapter:
    """Placeholder that makes live access opt-in rather than accidental."""

    def explore_usage(self) -> list[ExploreUsage]:
        raise LiveLookerNotConfigured("live Looker L1 access is not configured")

    def content_references(self) -> list[ContentReference]:
        raise LiveLookerNotConfigured("live Looker L1 access is not configured")

    def pdt_builds(self) -> list[PDTBuild]:
        raise LiveLookerNotConfigured("live Looker L1 access is not configured")


@dataclass(frozen=True)
class LookerToken:
    """A stored access token, bound to the Looker API origin that issued it (`looker_url`).

    Looker also returns a refresh token, but its guide documents no refresh request, so Strata
    does not persist it: an expired access token means `strata auth login` again.
    """

    access_token: str
    looker_url: str
    token_type: str = "Bearer"
    expires_at: float | None = None
    client_id: str = DEFAULT_CLIENT_ID
    redirect_uri: str = DEFAULT_REDIRECT_URI

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> LookerToken:
        token = data.get("access_token")
        if not token:
            raise LiveLookerNotConfigured("Looker token file is missing access_token")
        if not data.get("looker_url"):
            raise LiveLookerNotConfigured(
                "Looker token file has no looker_url, so it cannot be bound to an instance; "
                "run `strata auth login` again"
            )
        return cls(
            access_token=str(token),
            looker_url=_normalize_url(str(data["looker_url"])),
            token_type=str(data.get("token_type", "Bearer")),
            expires_at=float(data["expires_at"]) if data.get("expires_at") else None,
            client_id=str(data.get("client_id") or data.get("client_guid") or DEFAULT_CLIENT_ID),
            redirect_uri=str(data.get("redirect_uri", DEFAULT_REDIRECT_URI)),
        )

    def redacted(self) -> dict[str, Any]:
        data = asdict(self)
        data["access_token"] = _redact(self.access_token)
        return data

    def ensure_usable_for(self, url: str) -> None:
        """Refuse to present this token anywhere but its own origin, or after it expires."""
        if _origin(url) != _origin(self.looker_url):
            scheme, host, port = _origin(url)
            raise LiveLookerNotConfigured(
                f"refusing to send the Looker token issued for {self.looker_url} to "
                f"{scheme}://{host}:{port}. Pass --looker-url {self.looker_url} (the API host "
                "the token was issued for), or run `strata auth login` for the other instance"
            )
        if self.expires_at is not None and time.time() >= self.expires_at - EXPIRY_SKEW_SECONDS:
            raise LiveLookerNotConfigured("Looker token has expired; run `strata auth login` again")


def load_token(path: str | Path = DEFAULT_TOKEN_PATH) -> LookerToken:
    """Read the token file. On POSIX a file readable or writable by group/others is refused.

    Windows has no POSIX mode bits to check (Python reports synthetic ones), so the check is
    skipped there; rely on the user profile's ACLs.
    """
    token_path = Path(path).expanduser()
    if not token_path.exists():
        raise LiveLookerNotConfigured(f"Looker token file not found: {token_path}")
    if os.name == "posix":
        mode = stat.S_IMODE(token_path.stat().st_mode)
        if mode & 0o077:
            raise LiveLookerNotConfigured(
                f"refusing to read {token_path}: permissions {oct(mode)} allow group/other "
                f"access. Run: chmod 600 {token_path}"
            )
    return LookerToken.from_mapping(json.loads(token_path.read_text(encoding="utf-8")))


def prepare_token_dir(path: str | Path = DEFAULT_TOKEN_PATH) -> Path:
    """Make sure the token's directory is private before anything is written there (POSIX).

    A missing directory (and any missing parent) is created 0700. Strata's own `~/.strata` is tightened to 0700. Any
    other existing directory is never chmod-ed: if group or others can access it, the token
    path is refused, so pick a dedicated directory.
    """
    token_path = Path(path).expanduser()
    parent = token_path.parent
    own = parent.exists() and parent.resolve() == DEFAULT_TOKEN_PATH.parent.resolve()
    if (
        parent.exists()
        and os.name == "posix"
        and not own
        and stat.S_IMODE(parent.stat().st_mode) & 0o077
    ):
        raise LiveLookerNotConfigured(
            f"refusing to store the token in {parent}: the directory is accessible by "
            "group/other. Use a dedicated directory with mode 0700 (the default is "
            f"{DEFAULT_TOKEN_PATH})"
        )
    ensure_private_dir(parent, tighten=own)
    return token_path


def save_token(token: LookerToken, path: str | Path = DEFAULT_TOKEN_PATH) -> None:
    """Write the token as 0600 in a private directory, atomically.

    The file is created fresh with O_EXCL at mode 0600 (never briefly wider), then renamed over
    the target. The directory rules are `prepare_token_dir`'s.
    """
    token_path = prepare_token_dir(path)
    parent = token_path.parent
    tmp = parent / f".{token_path.name}.{secrets.token_hex(8)}.tmp"
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(tmp, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(token), indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, token_path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def auth_url(
    looker_url: str,
    state: str,
    code_challenge: str,
    client_id: str = DEFAULT_CLIENT_ID,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
) -> str:
    """The `/auth` URL on the Looker UI host, with `state` and an S256 PKCE challenge."""
    base = _normalize_url(looker_url)
    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": OAUTH_SCOPE,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
        }
    )
    return f"{base}/auth?{query}"


def exchange_code(
    api_url: str,
    code: str,
    code_verifier: str,
    client_id: str = DEFAULT_CLIENT_ID,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
    runner: LookerQueryRunner | None = None,
) -> LookerToken:
    """Redeem the code at `/api/token` on the Looker API host (JSON body, per the Looker guide)."""
    api = runner or LookerQueryRunner(api_url)
    payload = api.post_json(
        "/api/token",
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "code": code,
            "code_verifier": code_verifier,
        },
        content_type="application/json;charset=UTF-8",
    )
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise LookerAPIError("Looker token response had no access_token")
    expires_in = payload.get("expires_in")
    return LookerToken(
        access_token=str(payload["access_token"]),
        looker_url=api.looker_url,
        token_type=str(payload.get("token_type", "Bearer")),
        expires_at=time.time() + float(expires_in) if expires_in else None,
        client_id=client_id,
        redirect_uri=redirect_uri,
    )


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """urllib would re-send the Authorization header to a redirect target on any host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


_OPENER = urllib.request.build_opener(_RefuseRedirects)


class LookerQueryRunner:
    """Small stdlib HTTP runner for read-only Looker API calls."""

    def __init__(
        self, looker_url: str, token: LookerToken | None = None, timeout: int = 30
    ) -> None:
        if not looker_url:
            raise LiveLookerNotConfigured("--looker-url is required for live Looker access")
        self.looker_url = _normalize_url(looker_url)
        self.token = token
        self.timeout = timeout
        if token is not None:
            token.ensure_usable_for(self.looker_url)

    def run_inline_query(
        self, model: str, explore: str, fields: list[str], filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        payload = {
            "model": model,
            "view": explore,
            "fields": fields,
            "filters": filters or {},
            "limit": "5000",
        }
        return self.post_json(f"/api/{API_VERSION}/queries/run/json", payload)

    def post_json(
        self, path: str, payload: dict[str, Any], content_type: str = "application/json"
    ) -> Any:
        url = f"{self.looker_url}{path}"
        headers = {"Content-Type": content_type, "Accept": "application/json"}
        if self.token is not None:
            # Re-checked per request: origin binding and expiry hold for every call, not just
            # at construction.
            self.token.ensure_usable_for(url)
            headers["Authorization"] = f"Bearer {self.token.access_token}"
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
        )
        try:
            with _OPENER.open(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            # The response body is deliberately not echoed: on /api/token it can carry the code
            # or token material back.
            raise LookerAPIError(
                f"Looker API request to {path} failed: HTTP {exc.code} {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise LookerAPIError(f"Looker API request to {path} failed: {exc.reason}") from exc
        return json.loads(raw) if raw else {}


class LookerSystemActivityProvider:
    """UsageProvider implementation backed by read-only System Activity queries."""

    def __init__(self, runner: LookerQueryRunner, days: int = 30) -> None:
        if days <= 0:
            raise ValueError("days must be positive")
        self.runner = runner
        self.days = days

    @classmethod
    def from_config(
        cls,
        looker_url: str | None = None,
        token_path: str | Path = DEFAULT_TOKEN_PATH,
        days: int = 30,
    ) -> LookerSystemActivityProvider:
        token = load_token(token_path)
        # The token is bound to the origin it was issued for; a different --looker-url is
        # refused by the runner rather than sent the token.
        return cls(LookerQueryRunner(looker_url or token.looker_url, token), days=days)

    def period(self) -> dict[str, Any]:
        """The actual window `self.days` queries — same `{start, end, days}` shape the
        fixture path reads off its usage-facts JSON (`l1/fixtures.py`'s `load_usage_facts`).
        `run_inline_query`'s `f"{self.days} days"` filter is relative to now, so the window
        end is "now", not the last event date — this mirrors that."""
        end = datetime.now(UTC)
        start = end - timedelta(days=self.days)
        return {"start": start.date().isoformat(), "end": end.date().isoformat(), "days": self.days}

    def explore_usage(self) -> list[ExploreUsage]:
        rows = self.runner.run_inline_query(
            "system__activity",
            "history",
            ["query.model", "query.view", "history.query_run_count", "history.created_time"],
            {"history.created_date": f"{self.days} days"},
        )
        by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            model = _first(row, "query.model", "model")
            explore = _first(row, "query.view", "query.explore", "explore")
            if not model or not explore:
                continue
            current = by_key.setdefault(
                (model, explore), {"query_count": 0, "last_queried_at": None}
            )
            current["query_count"] += _int(
                _first(row, "history.query_run_count", "query_count") or 1
            )
            current["last_queried_at"] = _latest_iso(
                current["last_queried_at"], _first(row, "history.created_time", "created_at")
            )
        return [
            ExploreUsage(
                model=model,
                explore=explore,
                query_count=data["query_count"],
                last_queried_at=data["last_queried_at"],
            )
            for (model, explore), data in sorted(by_key.items())
        ]

    def content_references(self) -> list[ContentReference]:
        rows = self.runner.run_inline_query(
            "system__activity",
            "content_usage",
            [
                "content_usage.content_id",
                "content_usage.content_type",
                "query.model",
                "query.view",
                "content_usage.title",
            ],
            {"content_usage.last_viewed_date": f"{self.days} days"},
        )
        refs: list[ContentReference] = []
        for row in rows:
            model = _first(row, "query.model", "model")
            explore = _first(row, "query.view", "query.explore", "explore")
            content_id = _first(row, "content_usage.content_id", "content_id")
            if not model or not explore or not content_id:
                continue
            refs.append(
                ContentReference(
                    content_id=str(content_id),
                    content_type=str(
                        _first(row, "content_usage.content_type", "content_type") or "unknown"
                    ),
                    model=model,
                    explore=explore,
                    title=str(_first(row, "content_usage.title", "title") or ""),
                )
            )
        return sorted(refs, key=lambda item: (item.model, item.explore, item.content_id))

    def pdt_builds(self) -> list[PDTBuild]:
        rows = self.runner.run_inline_query(
            "system__activity",
            "pdt_event_log",
            [
                "pdt_event_log.view_name",
                "pdt_event_log.created_time",
                "pdt_event_log.connection",
                "pdt_event_log.bytes_processed",
            ],
            {"pdt_event_log.created_date": f"{self.days} days"},
        )
        by_view: dict[str, dict[str, Any]] = {}
        for row in rows:
            view = _first(row, "pdt_event_log.view_name", "view")
            if not view:
                continue
            current = by_view.setdefault(
                view,
                {
                    "build_count": 0,
                    "last_built_at": None,
                    "bytes_processed": 0,
                    "estimated_cost_usd": 0.0,
                },
            )
            bytes_processed = _int(_first(row, "pdt_event_log.bytes_processed", "bytes_processed"))
            current["build_count"] += 1
            current["last_built_at"] = _latest_iso(
                current["last_built_at"], _first(row, "pdt_event_log.created_time", "built_at")
            )
            current["bytes_processed"] += bytes_processed
            current["estimated_cost_usd"] += bytes_processed / 1_000_000_000_000 * 5.0
        return [
            PDTBuild(
                view=view,
                build_count=data["build_count"],
                last_built_at=data["last_built_at"],
                bytes_processed=data["bytes_processed"],
                estimated_cost_usd=round(data["estimated_cost_usd"], 6),
            )
            for view, data in sorted(by_view.items())
        ]


def _normalize_url(value: str) -> str:
    value = value.rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in ("https", "http"):
        raise ValueError(f"Looker URL must start with https://. Got: {value!r}")
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1"):
        raise ValueError(
            f"Looker URL must use https://. Got: {value!r}. http:// is only allowed for localhost."
        )
    return value


def _origin(url: str) -> tuple[str, str, int]:
    """(scheme, host, effective port) — the unit a token is bound to."""
    parts = urllib.parse.urlsplit(url)
    scheme = parts.scheme.lower()
    port = parts.port or (443 if scheme == "https" else 80)
    return scheme, (parts.hostname or "").lower(), port


def _redact(value: str) -> str:
    """At most the last four characters of a secret, and none of a short one."""
    return f"...{value[-4:]}" if len(value) >= 16 else "***"


def _first(row: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value not in {None, ""}:
            return str(value)
    return None


def _int(value: Any) -> int:
    if value in {None, ""}:
        return 0
    return int(float(value))
