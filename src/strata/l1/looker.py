"""Read-only Looker/System Activity provider for live L1 enrichment."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from strata.l1.types import ContentReference, ExploreUsage, PDTBuild

DEFAULT_CLIENT_GUID = "com.gsanalytics.strata.cli"
DEFAULT_REDIRECT_URI = "http://localhost:8765/oauth/callback"
DEFAULT_TOKEN_PATH = Path.home() / ".strata" / "tokens.json"
API_VERSION = "4.0"


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
    access_token: str
    token_type: str = "Bearer"
    expires_at: float | None = None
    refresh_token: str | None = None
    looker_url: str | None = None
    client_guid: str = DEFAULT_CLIENT_GUID
    redirect_uri: str = DEFAULT_REDIRECT_URI

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> LookerToken:
        token = data.get("access_token")
        if not token:
            raise LiveLookerNotConfigured("Looker token file is missing access_token")
        return cls(
            access_token=str(token),
            token_type=str(data.get("token_type", "Bearer")),
            expires_at=float(data["expires_at"]) if data.get("expires_at") else None,
            refresh_token=str(data["refresh_token"]) if data.get("refresh_token") else None,
            looker_url=str(data["looker_url"]) if data.get("looker_url") else None,
            client_guid=str(data.get("client_guid", DEFAULT_CLIENT_GUID)),
            redirect_uri=str(data.get("redirect_uri", DEFAULT_REDIRECT_URI)),
        )

    def redacted(self) -> dict[str, Any]:
        data = asdict(self)
        data["access_token"] = _redact(self.access_token)
        if self.refresh_token:
            data["refresh_token"] = _redact(self.refresh_token)
        return data


def load_token(path: str | Path = DEFAULT_TOKEN_PATH) -> LookerToken:
    token_path = Path(path).expanduser()
    if not token_path.exists():
        raise LiveLookerNotConfigured(f"Looker token file not found: {token_path}")
    mode = token_path.stat().st_mode & 0o177
    if mode != 0:
        import warnings

        warnings.warn(
            f"Token file {token_path} has loose permissions ({oct(token_path.stat().st_mode)[-4:]}). "
            "Expected 0600. Run: chmod 600 " + str(token_path),
            stacklevel=2,
        )
    return LookerToken.from_mapping(json.loads(token_path.read_text(encoding="utf-8")))


def save_token(token: LookerToken, path: str | Path = DEFAULT_TOKEN_PATH) -> None:
    token_path = Path(path).expanduser()
    token_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    token_path.write_text(
        json.dumps(asdict(token), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    token_path.chmod(0o600)


def auth_url(
    looker_url: str,
    client_guid: str = DEFAULT_CLIENT_GUID,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
) -> str:
    base = _normalize_url(looker_url)
    query = urllib.parse.urlencode(
        {"client_guid": client_guid, "redirect_uri": redirect_uri, "response_type": "code"}
    )
    return f"{base}/auth?{query}"


def exchange_code(
    looker_url: str,
    code: str,
    client_guid: str = DEFAULT_CLIENT_GUID,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
    runner: LookerQueryRunner | None = None,
) -> LookerToken:
    api = runner or LookerQueryRunner(looker_url)
    payload = api.post_form(
        "/token",
        {
            "grant_type": "authorization_code",
            "code": code,
            "client_guid": client_guid,
            "redirect_uri": redirect_uri,
        },
        auth_token=None,
    )
    expires_in = payload.get("expires_in")
    return LookerToken(
        access_token=str(payload["access_token"]),
        token_type=str(payload.get("token_type", "Bearer")),
        expires_at=time.time() + float(expires_in) if expires_in else None,
        refresh_token=str(payload["refresh_token"]) if payload.get("refresh_token") else None,
        looker_url=_normalize_url(looker_url),
        client_guid=client_guid,
        redirect_uri=redirect_uri,
    )


class LookerQueryRunner:
    """Small stdlib HTTP runner for read-only Looker API calls."""

    def __init__(self, looker_url: str, access_token: str | None = None, timeout: int = 30) -> None:
        if not looker_url:
            raise LiveLookerNotConfigured("--looker-url is required for live Looker access")
        self.looker_url = _normalize_url(looker_url)
        self.access_token = access_token
        self.timeout = timeout

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

    def post_json(self, path: str, payload: dict[str, Any], auth_token: str | None = None) -> Any:
        body = json.dumps(payload).encode("utf-8")
        return self._request(path, body, "application/json", auth_token)

    def post_form(
        self, path: str, payload: dict[str, Any], auth_token: str | None = None
    ) -> dict[str, Any]:
        body = urllib.parse.urlencode(payload).encode("utf-8")
        return self._request(path, body, "application/x-www-form-urlencoded", auth_token)

    def _request(
        self, path: str, body: bytes, content_type: str, auth_token: str | None = None
    ) -> Any:
        token = self.access_token if auth_token is None else auth_token
        headers = {"Content-Type": content_type, "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"{self.looker_url}{path}", data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise LookerAPIError(f"Looker API request failed: HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise LookerAPIError(f"Looker API request failed: {exc.reason}") from exc
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
        url = looker_url or token.looker_url
        if not url:
            raise LiveLookerNotConfigured(
                "--looker-url is required and token file has no looker_url"
            )
        return cls(LookerQueryRunner(url, token.access_token), days=days)

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


def _redact(value: str) -> str:
    return f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"


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


def _latest_iso(current: str | None, candidate: Any) -> str | None:
    if not candidate:
        return current
    candidate_str = str(candidate)
    if current is None or candidate_str > current:
        return candidate_str
    return current
