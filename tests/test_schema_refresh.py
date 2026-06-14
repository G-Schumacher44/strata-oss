"""Dry-run tests for generate_schema_facts.py — no BQ connection needed."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_schema_facts.py"
ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
ENTERPRISE_FIXTURE = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
GCS = ROOT / "tests" / "lookml" / "gcs_analytics"


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_dry_run_enterprise_mono(tmp_path):
    out = tmp_path / "schema.json"
    result = _run(["--repo", str(ENTERPRISE), "--out", str(out), "--dry-run"])

    assert result.returncode == 0, result.stderr
    assert "Physical tables in IR: 12" in result.stdout
    assert "Queryable (have BQ dataset): 12" in result.stdout
    # CTE false positives (clv_base, enriched, scored) no longer appear as physical_table nodes
    assert "Skipped" not in result.stdout
    assert "acme-analytics.gold_marts" in result.stdout
    assert "acme-analytics.silver" in result.stdout
    assert "INFORMATION_SCHEMA.COLUMNS" in result.stdout
    # No output file written in dry-run
    assert not out.exists()


def test_dry_run_with_existing_fixture(tmp_path):
    out = tmp_path / "schema.json"
    result = _run(
        [
            "--repo",
            str(ENTERPRISE),
            "--out",
            str(out),
            "--existing",
            str(ENTERPRISE_FIXTURE),
            "--dry-run",
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "Tables in fixture:" in result.stdout
    assert "Tables also in IR:" in result.stdout


def test_dry_run_gcs_analytics(tmp_path):
    out = tmp_path / "schema.json"
    result = _run(["--repo", str(GCS), "--out", str(out), "--dry-run"])

    assert result.returncode == 0, result.stderr
    assert "Physical tables in IR:" in result.stdout
    assert "dry-run" in result.stdout.lower()


def test_dry_run_two_part_table_with_bq_project(tmp_path):
    """2-part table names resolve when --bq-project is supplied."""
    out = tmp_path / "schema.json"
    result = _run(
        [
            "--repo",
            str(GCS),
            "--out",
            str(out),
            "--bq-project",
            "my-project",
            "--dry-run",
        ]
    )
    assert result.returncode == 0, result.stderr
