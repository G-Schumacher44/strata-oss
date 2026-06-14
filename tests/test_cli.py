"""CLI smoke tests — verifies strata subcommands run and return expected output."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
ENTERPRISE = REPO_ROOT / "tests" / "lookml" / "enterprise_mono"
ENTERPRISE_USAGE = FIXTURES / "enterprise_usage_facts.json"
ENTERPRISE_SCHEMA = FIXTURES / "enterprise_schema_facts.json"

CLI = [sys.executable, "-m", "strata.cli.main"]


def run(*args, env_extra=None):
    import os

    env = {**os.environ, **(env_extra or {})}
    return subprocess.run(
        [*CLI, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


# ── strata mcp validate ───────────────────────────────────────────────────────


def test_mcp_validate_passes_with_valid_repo(tmp_path):
    result = run("mcp", "validate", env_extra={"STRATA_REPO_PATH": str(FIXTURES)})
    assert result.returncode == 0, result.stderr
    assert "repo path exists" in result.stdout
    assert "skills:" in result.stdout
    assert "chart templates:" in result.stdout


def test_mcp_validate_fails_on_missing_repo(tmp_path):
    result = run("mcp", "validate", env_extra={"STRATA_REPO_PATH": str(tmp_path / "nonexistent")})
    assert result.returncode == 1
    assert "does not exist" in result.stdout


# ── strata mcp config ─────────────────────────────────────────────────────────


def test_mcp_config_returns_json(tmp_path):
    result = run("mcp", "config", env_extra={"STRATA_REPO_PATH": str(FIXTURES)})
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    assert "repo_path" in config
    assert "skills_path" in config
    assert "bq_project" in config
    assert "cost_threshold_gb" in config
    assert config["cost_threshold_gb"] == 100.0


# ── strata query status ───────────────────────────────────────────────────────


def test_query_status_returns_ir_summary():
    result = run(
        "query",
        "status",
        env_extra={
            "STRATA_REPO_PATH": str(FIXTURES),
            "STRATA_USAGE_FIXTURE": str(FIXTURES / "usage_facts.json"),
        },
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["node_counts"]["view"] == 9
    assert data["edge_count"] > 0


# ── strata query field ────────────────────────────────────────────────────────


def test_query_field_returns_field_definition():
    result = run(
        "query",
        "field",
        "customer_extended",
        "email",
        env_extra={"STRATA_REPO_PATH": str(FIXTURES)},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["type"] == "string"
    assert "sql" in data


def test_query_field_missing_returns_error():
    result = run(
        "query",
        "field",
        "nonexistent_view",
        "nonexistent_field",
        env_extra={"STRATA_REPO_PATH": str(FIXTURES)},
    )
    assert result.returncode != 0 or "not found" in result.stdout + result.stderr


# ── strata query explore ──────────────────────────────────────────────────────


def test_query_explore_returns_deps():
    result = run(
        "query",
        "explore",
        "refined_customer",
        "refined_explore",
        env_extra={"STRATA_REPO_PATH": str(FIXTURES)},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["base_view"] == "customer_extended"
    assert "joins" in data


# ── strata query orphans ──────────────────────────────────────────────────────


def test_query_orphans_returns_list():
    result = run(
        "query",
        "orphans",
        "--kind",
        "view",
        env_extra={"STRATA_REPO_PATH": str(FIXTURES)},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    names = [d["name"] for d in data]
    assert "orphan_view" in names


# ── strata query impact ───────────────────────────────────────────────────────


def test_query_impact_returns_blast_radius():
    result = run(
        "query",
        "impact",
        "analytics.orders",
        env_extra={"STRATA_REPO_PATH": str(FIXTURES)},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "views" in data
    assert "pdt_orders" in data["views"]


# ── strata query scope ────────────────────────────────────────────────────────


def test_query_scope_returns_impacted_explores():
    result = run(
        "query",
        "scope",
        "customer_extended.view.lkml",
        env_extra={"STRATA_REPO_PATH": str(FIXTURES)},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "explores" in data
    explore_names = [e["explore"] for e in data["explores"]]
    assert "refined_customer" in explore_names


# ── strata generate-schema --dry-run ──────────────────────────────────────────


# ── strata skill ──────────────────────────────────────────────────────────────


def test_skill_list_shows_catalog():
    result = run("skill", "list")
    assert result.returncode == 0, result.stderr
    assert "lookml_ticket_navigator" in result.stdout
    assert "bq_schema_probe" in result.stdout


def test_skill_show_returns_full_procedure():
    result = run("skill", "lookml_ticket_navigator")
    assert result.returncode == 0, result.stderr
    assert "## Procedure" in result.stdout
    assert "strata_navigate" in result.stdout


def test_skill_missing_exits_nonzero():
    result = run("skill", "no_such_skill_xyz")
    assert result.returncode == 1
    assert "not found" in result.stderr


# ── strata bootstrap repo_path guard ──────────────────────────────────────────


def test_bootstrap_reprompts_on_nonexistent_repo_path(tmp_path):
    import click
    from click.testing import CliRunner

    from strata.cli.bootstrap import _prompt_repo_path

    @click.command()
    def harness():
        click.echo("RESULT=" + _prompt_repo_path("/nope/does/not/exist", str(tmp_path)))

    # enter bad path -> decline "save anyway" -> enter a valid path
    result = CliRunner().invoke(harness, input=f"/nope/does/not/exist\nn\n{tmp_path}\n")
    assert result.exit_code == 0, result.output
    assert "path does not exist" in result.output
    assert f"RESULT={tmp_path}" in result.output


def test_bootstrap_allows_saving_bad_path_when_confirmed():
    import click
    from click.testing import CliRunner

    from strata.cli.bootstrap import _prompt_repo_path

    @click.command()
    def harness():
        click.echo("RESULT=" + _prompt_repo_path("/nope/x", "/tmp"))

    # bad path -> explicitly confirm "save anyway" -> keeps it (escape hatch)
    result = CliRunner().invoke(harness, input="/nope/x\ny\n")
    assert result.exit_code == 0, result.output
    assert "RESULT=/nope/x" in result.output


def test_mcp_validate_names_repo_source(tmp_path):
    result = run("mcp", "validate", env_extra={"STRATA_REPO_PATH": str(tmp_path)})
    assert result.returncode == 0
    assert "from STRATA_REPO_PATH env" in result.stdout


def test_mcp_validate_bad_env_path_blames_env_not_config(tmp_path):
    missing = tmp_path / "does_not_exist"
    result = run("mcp", "validate", env_extra={"STRATA_REPO_PATH": str(missing)})
    assert result.returncode == 1
    assert "repo path does not exist" in result.stdout
    # remediation must point at the winning source (env), not misdirect to the config
    assert "STRATA_REPO_PATH" in result.stdout
    assert "fix repo_path in ~/.strata/config.json" not in result.stdout


def test_generate_schema_dry_run(tmp_path):
    result = run(
        "generate-schema",
        "--repo",
        str(FIXTURES),
        "--out",
        str(tmp_path / "schema_facts.json"),
        "--dry-run",
    )
    assert result.returncode == 0, result.stderr
    assert "dry-run" in result.stdout.lower() or "dry" in result.stdout.lower()
    assert not (tmp_path / "schema_facts.json").exists()
