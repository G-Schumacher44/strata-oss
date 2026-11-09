"""Workbench links out (S11): a base URL resolves in one place; with none, no output changes."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client

from strata_lookml.config import load_workbench_url
from strata_lookml.errors import InvalidInput
from strata_lookml.links import finding_path, link
from strata_lookml.mcp.server import create_server
from strata_lookml.outputs.pr_report import build_pr_comment
from strata_lookml.pipeline import build_graph

ROOT = Path(__file__).resolve().parent
GCS = ROOT / "lookml" / "gcs_analytics"
MONO = ROOT / "lookml" / "enterprise_mono"
SCHEMA = ROOT / "fixtures" / "gcs_schema_facts.json"
USAGE = ROOT / "fixtures" / "enterprise_usage_facts.json"
SERVER = "http://127.0.0.1:8765"


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("STRATA_WORKBENCH_URL", raising=False)


def _check(*args, env=None):
    return subprocess.run(
        [sys.executable, "-m", "strata_lookml.cli.main", "check", "--repo", str(GCS),
         "--schema-fixture", str(SCHEMA), "--fail-on", "drift", *args],
        capture_output=True, text=True, check=False, env={**os.environ, **(env or {})},
    )  # fmt: skip


def _config(tmp_path, **data):
    (tmp_path / ".strata").mkdir(exist_ok=True)
    (tmp_path / ".strata" / "config.json").write_text(json.dumps(data))


def test_no_base_resolves_to_none_and_adds_no_url_keys():
    assert load_workbench_url() is None
    result = _check("--json")
    assert result.returncode == 1
    failures = json.loads(result.stdout)["failures"]
    assert failures and all("url" not in f for f in failures)
    assert "<http" not in result.stderr


def test_server_base_gives_path_form_urls_in_json_and_text():
    result = _check("--json", "--workbench-url", SERVER)
    for f in json.loads(result.stdout)["failures"]:
        assert f["url"] == f"{SERVER}{finding_path(f['id'])}"
    text = _check("--workbench-url", SERVER)
    assert f"<{SERVER}/finding/" in text.stderr


def test_export_base_gives_hash_form():
    result = _check("--json", "--workbench-url", "report.html")
    for f in json.loads(result.stdout)["failures"]:
        assert f["url"] == f"report.html#{finding_path(f['id'])}"


def test_special_characters_are_quoted_and_round_trip():
    from urllib.parse import unquote

    url = link(SERVER, finding_path("foo bar:baz/qux"))
    assert url == f"{SERVER}/finding/foo%20bar%3Abaz%2Fqux"
    assert unquote(url.rsplit("/", 1)[1]) == "foo bar:baz/qux"


def test_precedence_flag_over_env_over_config(tmp_path, monkeypatch):
    _config(tmp_path, workbench_url="http://config:1")
    assert load_workbench_url() == "http://config:1"
    monkeypatch.setenv("STRATA_WORKBENCH_URL", "http://env:2")
    assert load_workbench_url() == "http://env:2"
    assert load_workbench_url("http://flag:3") == "http://flag:3"


@pytest.mark.parametrize("bad", ["localhost:8765", "ftp://x", "/some/dir", "http://"])
def test_invalid_base_is_invalid_input_with_hint(bad):
    with pytest.raises(InvalidInput) as exc:
        load_workbench_url(bad)
    assert exc.value.hint


def test_invalid_base_exits_1_with_hint():
    result = _check("--workbench-url", "nonsense")
    assert result.returncode == 1
    assert "Hint:" in result.stderr


def test_pr_report_links_only_with_a_base():
    scope = {"explores": [{"model": "m", "explore": "e", "impacted_views": ["v"]}]}
    args = (["a.lkml"], {"a.lkml": ["v"]}, scope, [])
    plain = build_pr_comment(*args)
    assert "http" not in plain and "- `m.e`" in plain
    assert build_pr_comment(*args, workbench_base=None) == plain
    linked = build_pr_comment(*args, workbench_base=SERVER)
    assert f"- [`m.e`]({SERVER}/explore/m.e)" in linked
    assert "- [`m.e`](r.html#/explore/m.e)" in build_pr_comment(*args, workbench_base="r.html")


def _mcp_object(monkeypatch, base):
    if base:
        monkeypatch.setenv("STRATA_WORKBENCH_URL", base)
    graph = build_graph(MONO, USAGE, None)

    async def call():
        async with Client(create_server(graph)) as client:
            res = await client.call_tool(
                "strata_object", {"kind": "view", "name": "fct_daily_dashboard"}
            )
            return json.loads(res.content[0].text)

    return asyncio.run(call())


def test_mcp_object_gains_workbench_url_only_with_a_base(monkeypatch):
    assert "workbench_url" not in _mcp_object(monkeypatch, None)
    assert _mcp_object(monkeypatch, SERVER)["workbench_url"] == f"{SERVER}/view/fct_daily_dashboard"
