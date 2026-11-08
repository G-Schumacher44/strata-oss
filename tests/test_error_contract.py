"""The one error contract (strata_lookml.errors): MCP isError + message, CLI exit 1 + envelope."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from mcp import Client

from strata_lookml.errors import NotFound
from strata_lookml.ir.resolver import build_resolved_graph
from strata_lookml.mcp.server import create_server
from strata_lookml.mcp.tools import strata_view_sources

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def _call_tool(name: str, arguments: dict):
    # In-process over the real server + client session: the SDK's own error handling decides
    # what the client sees, so a domain error raised as a plain exception is masked here.
    async def call():
        async with Client(create_server(build_resolved_graph(FIXTURES))) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(call())


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("strata_validation_scope", {"changed": ["view:"]}, "'<kind>:<name>'"),
        (
            "strata_render_chart",
            {"spec_yaml": "mark: bar", "data_json": "[]", "out_path": "/etc/x.html"},
            "out_path must be within",
        ),
        (
            "strata_render_chart",
            {"spec_yaml": "- bar", "data_json": "[]", "out_path": "/tmp/strata_contract.html"},
            "chart spec must be a mapping",
        ),
        ("strata_skill", {"name": "nope"}, "skill not found: nope"),
        ("strata_query_field", {"view": "v", "field": "nope"}, "field not found: v.nope"),
    ],
)
def test_mcp_domain_error_reaches_the_client(name, arguments, message):
    result = _call_tool(name, arguments)

    assert result.is_error is True
    assert message in result.content[0].text


def test_unknown_model_in_view_sources_raises():
    with pytest.raises(NotFound, match="model not found: nope") as err:
        strata_view_sources(build_resolved_graph(FIXTURES), model="nope")
    assert "Known models:" in (err.value.hint or "")


def _cli(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "strata_lookml.cli.main", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env_extra or {})},
    )


def test_cli_not_found_exits_1_with_json_envelope_and_hint():
    result = _cli("query", "field", "v", "nope", "--repo", str(FIXTURES))

    assert result.returncode == 1, result.stderr
    envelope = json.loads(result.stdout)
    assert envelope["error"] == "field not found: v.nope"
    assert envelope["code"] == "not_found"
    assert "find-field" in envelope["hint"]
    assert "Error: field not found: v.nope" in result.stderr
    assert "Hint: " in result.stderr


@pytest.mark.parametrize(
    ("repo", "code"), [("/nonexistent", "not_found"), ("EMPTY", "invalid_input")]
)
def test_cli_missing_or_empty_repo_exits_1(repo, code, tmp_path):
    repo_arg = str(tmp_path) if repo == "EMPTY" else repo
    result = _cli("query", "status", "--repo", repo_arg)

    assert result.returncode == 1, result.stdout
    assert json.loads(result.stdout)["code"] == code
    assert "STRATA_REPO_PATH" in result.stderr


def test_cli_json_envelope_only_when_json_flag_is_set():
    anchor = "zzz_not_a_thing_anywhere"
    human = _cli("query", "navigate", anchor, "--repo", str(FIXTURES))
    as_json = _cli("query", "navigate", anchor, "--repo", str(FIXTURES), "--json")

    assert human.returncode == as_json.returncode == 1
    assert human.stdout == ""
    assert json.loads(as_json.stdout)["code"] == "not_found"


def test_auth_status_without_token_points_at_login(tmp_path):
    result = _cli("auth", "status", "--token-path", str(tmp_path / "token.json"))

    assert result.returncode == 1
    assert "strata auth login" in result.stderr


def test_strata_chart_reports_contract_errors_without_traceback(tmp_path, monkeypatch, capsys):
    from strata_lookml.viz import render

    spec = tmp_path / "spec.yml"
    spec.write_text("- not a mapping\n", encoding="utf-8")
    data = tmp_path / "data.json"
    data.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["strata-chart", "--spec", str(spec), str(data)])

    with pytest.raises(SystemExit) as exc:
        render.main()

    assert exc.value.code == 1
    assert "Error: chart spec must be a mapping" in capsys.readouterr().err
