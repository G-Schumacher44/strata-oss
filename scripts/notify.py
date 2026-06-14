#!/usr/bin/env python3
"""Build Slack/Jira notification payloads from Strata artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from strata.outputs.notifications import (  # noqa: E402
    build_jira_tickets,
    build_slack_payload,
    load_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", default=str(REPO_ROOT / "output" / "gcs_analytics"))
    parser.add_argument("--repo-name", default="gcs_analytics")
    parser.add_argument("--jira-project", default="DATA")
    parser.add_argument("--dry-run", action="store_true", help="Print payloads instead of sending")
    args = parser.parse_args()

    artifacts = load_artifacts(args.artifacts)
    payload = {
        "slack": build_slack_payload(artifacts, args.repo_name),
        "jira": build_jira_tickets(artifacts, args.jira_project),
    }
    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(
        "Sending notifications is not implemented; use --dry-run to inspect payloads.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
