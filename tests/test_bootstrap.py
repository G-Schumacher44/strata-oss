"""strata bootstrap: non-interactive, plan-then-apply, all-or-nothing (spec S6)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from strata_lookml.bootstrap import plan as plan_mod
from strata_lookml.cli.main import strata_cli as cli

FIXTURES = Path(__file__).parent / "fixtures"
USAGE = FIXTURES / "enterprise_usage_facts.json"
SCHEMA = FIXTURES / "enterprise_schema_facts.json"


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.delenv("STRATA_USAGE_FIXTURE", raising=False)
    monkeypatch.delenv("STRATA_SCHEMA_FIXTURE", raising=False)
    return h


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "lookml_repo"
    r.mkdir()
    (r / "a.view.lkml").write_text("view: a {}\n")
    return r


def snapshot(*roots: Path) -> dict[str, str]:
    out = {}
    for root in roots:
        for p in sorted(root.rglob("*")):
            key = str(p)
            out[key] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
    return out


def invoke(*args, **kw):
    return CliRunner().invoke(cli, ["bootstrap", *args], **kw)


def test_no_tty_without_yes_exits_2_and_writes_nothing(repo, home):
    before = snapshot(repo, home)
    result = invoke("--repo", str(repo), input="")  # stdin is not a tty
    assert result.exit_code == 2
    assert "--yes" in result.output
    assert snapshot(repo, home) == before


def test_yes_with_fixtures_writes_env_into_both_client_configs(repo, home):
    result = invoke(
        "--repo", str(repo), "--yes", "--usage-fixture", str(USAGE), "--schema-fixture", str(SCHEMA)
    )
    assert result.exit_code == 0, result.output
    for rel in (".mcp.json", ".cursor/mcp.json"):
        env = json.loads((repo / rel).read_text())["mcpServers"]["strata"]["env"]
        assert env["STRATA_REPO_PATH"] == str(repo.resolve())
        assert env["STRATA_USAGE_FIXTURE"] == str(USAGE.resolve())
        assert env["STRATA_SCHEMA_FIXTURE"] == str(SCHEMA.resolve())
    cfg = json.loads((home / ".strata" / "config.json").read_text())
    assert cfg == {"repo_path": str(repo.resolve()), "cost_threshold_gb": 100.0}


def test_yes_flags_set_config_and_keep_existing_default_repo(repo, home):
    (home / ".strata").mkdir()
    (home / ".strata" / "config.json").write_text(json.dumps({"repo_path": "/elsewhere"}))
    result = invoke(
        "--repo", str(repo), "--yes", "--bq-project", "proj", "--cost-threshold-gb", "5"
    )
    assert result.exit_code == 0, result.output
    cfg = json.loads((home / ".strata" / "config.json").read_text())
    assert cfg == {"repo_path": "/elsewhere", "bq_project": "proj", "cost_threshold_gb": 5.0}


def test_failure_on_fourth_write_leaves_no_new_files(repo, home, monkeypatch):
    before = snapshot(repo, home)
    real = plan_mod._replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 4:
            raise OSError("disk full")
        real(src, dst)

    monkeypatch.setattr(plan_mod, "_replace", flaky)
    result = invoke("--repo", str(repo), "--yes")
    assert calls["n"] == 4
    assert result.exit_code == 1
    assert "nothing was changed" in result.output
    assert snapshot(repo, home) == before  # no files, no leftover dirs, no temp files


def test_failure_restores_overwritten_files(repo, home, monkeypatch):
    (repo / "AGENTS.md").write_text("mine\n")
    before = snapshot(repo, home)
    real = plan_mod._replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("boom")
        real(src, dst)

    monkeypatch.setattr(plan_mod, "_replace", flaky)
    result = invoke("--repo", str(repo), "--yes", "--force")
    assert result.exit_code == 1
    assert snapshot(repo, home) == before


def test_dry_run_writes_nothing_and_lists_plan(repo, home):
    before = snapshot(repo, home)
    result = invoke("--repo", str(repo), "--dry-run")
    assert result.exit_code == 0, result.output
    assert "would write: .mcp.json" in result.output
    assert ".mcp.json" in result.output and "conductor/index.md" in result.output
    assert "nothing written" in result.output
    assert snapshot(repo, home) == before


def test_mcp_config_client_matches_bootstrap_output(repo, home):
    assert (
        invoke(
            "--repo",
            str(repo),
            "--yes",
            "--usage-fixture",
            str(USAGE),
            "--schema-fixture",
            str(SCHEMA),
        ).exit_code
        == 0
    )
    for client, rel in (("claude", ".mcp.json"), ("cursor", ".cursor/mcp.json")):
        result = CliRunner().invoke(
            cli,
            [
                "mcp", "config", "--client", client, "--repo", str(repo),
                "--usage-fixture", str(USAGE), "--schema-fixture", str(SCHEMA),
            ],
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        assert result.output == (repo / rel).read_text()


def test_conductor_init_still_works_and_is_idempotent(repo, home):
    runner = CliRunner()
    first = runner.invoke(cli, ["conductor", "init", "--repo", str(repo)])
    assert first.exit_code == 0, first.output
    assert (repo / "conductor" / "handoff-log.md").exists()
    assert (repo / "conductor" / "review").is_dir()
    second = runner.invoke(cli, ["conductor", "init", "--repo", str(repo)])
    assert "skip (exists)" in second.output
    assert os.listdir(repo / "conductor" / "templates")
