import json
import subprocess
import sys
from pathlib import Path

from strata.outputs.notifications import build_jira_tickets, build_slack_payload

ROOT = Path(__file__).resolve().parents[1]


def test_notification_payloads_are_deterministic():
    artifacts = {
        "usage_summary": {"explore_count": 2, "total_queries": 10},
        "dead_code_register": [{"name": "old"}],
        "schema_drift": [{"field": "missing"}],
        "pdt_ledger": [{"estimated_cost_usd": 12.5}],
        "cleanup_roadmap": [{"action": "review_for_deprecation", "target": "old"}],
    }

    slack = build_slack_payload(artifacts, "repo")
    jira = build_jira_tickets(artifacts, "DATA")

    assert slack["text"] == "Strata report for repo: 1 dead-code, 1 schema-drift, $12.50 PDT cost"
    assert jira[0]["fields"]["project"]["key"] == "DATA"
    assert "review_for_deprecation" in jira[0]["fields"]["summary"]


def test_notify_dry_run_cli(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    for name, payload in {
        "usage_summary": {"explore_count": 1, "total_queries": 2},
        "cleanup_roadmap": [{"action": "review", "target": "x"}],
    }.items():
        (artifacts / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "notify.py"),
            "--artifacts",
            str(artifacts),
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "slack" in payload
    assert "jira" in payload
