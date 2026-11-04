"""Notification payload builders for Strata reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_artifacts(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    return {item.stem: json.loads(item.read_text(encoding="utf-8")) for item in root.glob("*.json")}


def build_slack_payload(artifacts: dict[str, Any], repo_name: str = "strata") -> dict[str, Any]:
    summary = artifacts.get("usage_summary", {})
    dead = artifacts.get("dead_code_register", [])
    pdt = artifacts.get("pdt_ledger", [])
    drift = artifacts.get("schema_drift", [])
    cleanup = artifacts.get("cleanup_roadmap", [])
    cost = sum(float(item.get("estimated_cost_usd", 0)) for item in pdt)
    text = f"Strata report for {repo_name}: {len(dead)} dead-code, {len(drift)} schema-drift, ${cost:,.2f} PDT cost"
    return {
        "text": text,
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"Strata report: {repo_name}"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Explores:*\n{summary.get('explore_count', 0)}"},
                    {"type": "mrkdwn", "text": f"*Queries:*\n{summary.get('total_queries', 0)}"},
                    {"type": "mrkdwn", "text": f"*Dead code:*\n{len(dead)}"},
                    {"type": "mrkdwn", "text": f"*Schema drift:*\n{len(drift)}"},
                    {"type": "mrkdwn", "text": f"*PDT cost:*\n${cost:,.2f}"},
                    {"type": "mrkdwn", "text": f"*Cleanup items:*\n{len(cleanup)}"},
                ],
            },
        ],
    }


def build_jira_tickets(
    artifacts: dict[str, Any], project_key: str = "DATA"
) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    for item in artifacts.get("cleanup_roadmap", []):
        target = item.get("target", "unknown")
        action = item.get("action", "review")
        tickets.append(
            {
                "fields": {
                    "project": {"key": project_key},
                    "summary": f"Strata: {action} {target}",
                    "description": json.dumps(item, indent=2, sort_keys=True),
                    "issuetype": {"name": "Task"},
                    "labels": ["strata", "looker"],
                }
            }
        )
    return tickets
