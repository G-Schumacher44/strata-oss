import json
import subprocess
import sys
from pathlib import Path

import pytest

from strata.l1.looker import (
    LiveLookerNotConfigured,
    LookerSystemActivityProvider,
    LookerToken,
    auth_url,
    load_token,
    save_token,
)
from strata.pipeline import build_graph_with_provider

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


class FakeRunner:
    def __init__(self) -> None:
        self.calls = []

    def run_inline_query(self, model, explore, fields, filters=None):
        self.calls.append((model, explore, fields, filters))
        if explore == "history":
            return [
                {
                    "query.model": "test_model",
                    "query.view": "customer",
                    "history.query_run_count": "2",
                    "history.created_time": "2026-06-02T12:00:00Z",
                },
                {
                    "model": "test_model",
                    "explore": "customer",
                    "query_count": 3,
                    "created_at": "2026-06-03T12:00:00Z",
                },
            ]
        if explore == "content_usage":
            return [
                {
                    "content_id": "dash_1",
                    "content_type": "dashboard",
                    "model": "test_model",
                    "explore": "customer",
                    "title": "Exec",
                }
            ]
        if explore == "pdt_event_log":
            return [
                {
                    "view": "pdt_orders",
                    "bytes_processed": 1_000_000_000_000,
                    "built_at": "2026-06-03T01:00:00Z",
                }
            ]
        return []


def test_looker_provider_maps_system_activity_rows():
    provider = LookerSystemActivityProvider(FakeRunner(), days=7)
    facts = {item.key: item for item in provider.explore_usage()}

    assert facts["test_model.customer"].query_count == 5
    assert facts["test_model.customer"].last_queried_at == "2026-06-03T12:00:00Z"
    assert provider.content_references()[0].content_id == "dash_1"
    assert provider.pdt_builds()[0].estimated_cost_usd == 5.0


def test_build_graph_with_looker_provider_contract():
    graph = build_graph_with_provider(FIXTURES, LookerSystemActivityProvider(FakeRunner(), days=30))

    assert graph.metadata["l1"]["explore_usage"]["test_model.customer"]["query_count"] == 5
    assert graph.metadata["l1"]["pdt_ledger"][0]["view"] == "pdt_orders"


def test_missing_token_fails_fast(tmp_path):
    with pytest.raises(LiveLookerNotConfigured, match="token file not found"):
        LookerSystemActivityProvider.from_config(
            "https://example.looker.com", token_path=tmp_path / "missing.json"
        )


def test_token_status_redacts_secret(tmp_path):
    path = tmp_path / "tokens.json"
    save_token(
        LookerToken(access_token="abcdef1234567890", looker_url="https://example.looker.com"), path
    )

    token = load_token(path)
    assert token.access_token == "abcdef1234567890"
    assert token.redacted()["access_token"] == "abcd...7890"


def test_auth_url_uses_registered_client_guid_and_redirect():
    url = auth_url(
        "https://example.looker.com/", redirect_uri="http://localhost:8765/oauth/callback"
    )

    assert url.startswith("https://example.looker.com/auth?")
    assert "client_guid=com.gsanalytics.strata.cli" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Foauth%2Fcallback" in url


def test_strata_auth_status_cli(tmp_path):
    path = tmp_path / "tokens.json"
    save_token(
        LookerToken(access_token="abcdef1234567890", looker_url="https://example.looker.com"), path
    )
    result = subprocess.run(
        [sys.executable, "-m", "strata.cli.main", "auth", "status", "--token-path", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["access_token"] == "abcd...7890"
