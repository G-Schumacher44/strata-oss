"""`strata mcp validate`: pass / advisory / fail states, exit codes, --json (D8)."""

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from strata_lookml.cli.main import strata_cli

ROOT = Path(__file__).resolve().parents[1]
GCS = ROOT / "tests" / "lookml" / "gcs_analytics"
USAGE = ROOT / "tests" / "fixtures" / "gcs_usage_facts.json"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """HOME in tmp (never the real ~/.strata), no strata env, a scratch repo copy."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for var in (
        "STRATA_CACHE_PATH",
        "STRATA_REPO_PATH",
        "STRATA_USAGE_FIXTURE",
        "STRATA_SCHEMA_FIXTURE",
    ):
        monkeypatch.delenv(var, raising=False)
    repo = tmp_path / "gcs_analytics"
    shutil.copytree(GCS, repo, ignore=shutil.ignore_patterns(".git"))
    monkeypatch.setenv("STRATA_REPO_PATH", str(repo))
    monkeypatch.chdir(tmp_path)
    return tmp_path, repo


def _validate(*args):
    return CliRunner().invoke(strata_cli, ["mcp", "validate", *args])


def _statuses(result):
    return {c["name"]: c["status"] for c in json.loads(result.output)["checks"]}


def test_missing_configured_usage_fixture_is_a_hard_fail(env, monkeypatch):
    tmp, _ = env
    monkeypatch.setenv("STRATA_USAGE_FIXTURE", str(tmp / "nope.json"))
    result = _validate()
    assert result.exit_code == 1
    assert "✗ usage facts" in result.output


def test_unparseable_configured_schema_fixture_is_a_hard_fail(env, monkeypatch):
    tmp, _ = env
    bad = tmp / "bad.json"
    bad.write_text("{not json")
    monkeypatch.setenv("STRATA_SCHEMA_FIXTURE", str(bad))
    result = _validate("--json")
    assert result.exit_code == 1
    assert _statuses(result)["schema facts"] == "fail"


def test_missing_cache_is_advisory_not_a_failure(env):
    result = _validate()
    assert result.exit_code == 0, result.output
    assert "~ IR cache: not built yet" in result.output
    assert "strata build" in result.output
    assert "✗" not in result.output
    assert "MCP server is ready." in result.output


def test_repo_without_lkml_files_fails(env):
    tmp, _ = env
    empty = tmp / "empty"
    empty.mkdir()
    (empty / "README.md").write_text("no lookml here")
    result = _validate_env(empty)
    assert result.exit_code == 1
    assert "✗ LookML parse" in result.output


def _validate_env(repo):
    return CliRunner().invoke(strata_cli, ["mcp", "validate"], env={"STRATA_REPO_PATH": str(repo)})


def test_json_lists_checks_counts_and_ready(env, monkeypatch):
    monkeypatch.setenv("STRATA_USAGE_FIXTURE", str(USAGE))
    result = _validate("--json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ready"] is True
    assert payload["counts"]["nodes"] > 0
    for c in payload["checks"]:
        assert set(c) == {"name", "status", "message", "hint"}
        assert c["status"] in {"pass", "warn", "fail"}
    statuses = _statuses(result)
    assert statuses["LookML parse"] == "pass"
    assert statuses["usage facts"] == "pass"
    assert statuses["schema facts"] == "warn"
    assert statuses["IR cache"] == "warn"


def test_json_not_ready_exits_1(env):
    result = CliRunner().invoke(
        strata_cli,
        ["mcp", "validate", "--json"],
        env={"STRATA_REPO_PATH": str(env[0] / "missing")},
    )
    assert result.exit_code == 1
    assert json.loads(result.output)["ready"] is False


def test_output_never_mentions_strata_outputs(env, monkeypatch):
    for args in ([], ["--json"]):
        assert "strata outputs" not in _validate(*args).output
    monkeypatch.setenv("STRATA_USAGE_FIXTURE", str(env[0] / "nope.json"))
    assert "strata outputs" not in _validate().output


def test_strata_cache_path_is_honoured(env, monkeypatch):
    tmp, repo = env
    cache = tmp / "elsewhere" / "ir.db"
    monkeypatch.setenv("STRATA_CACHE_PATH", str(cache))
    assert _statuses(_validate("--json"))["IR cache"] == "warn"
    build = CliRunner().invoke(strata_cli, ["build", "--repo", str(repo)])
    assert build.exit_code == 0, build.output
    assert cache.exists()
    assert _statuses(_validate("--json"))["IR cache"] == "pass"
