#!/usr/bin/env python3
"""Post a Strata validation scope comment on a PR.

Detects which views are defined in the changed .lkml files, runs validation
scope analysis offline, and posts (or prints) a structured PR comment.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Hidden marker so the bot can find and update its own comment instead of
# posting a fresh one on every push (one always-current comment per PR).
BOT_MARKER = "<!-- strata-bot -->"

from strata.mcp.tools import strata_dead_code_register, strata_validation_scope  # noqa: E402
from strata.outputs.pr_report import build_pr_comment  # noqa: E402
from strata.pipeline import build_graph  # noqa: E402


def _files_to_views(graph, changed_files: list[str]) -> dict[str, list[str]]:
    """Map each changed file → view names it defines, using IR source_file."""
    repo = Path(graph.repo_path).as_posix().rstrip("/") + "/"
    relative_map: dict[str, str] = {}  # relative_path → original arg
    for f in changed_files:
        p = Path(f).as_posix()
        rel = p[len(repo) :] if p.startswith(repo) else p
        relative_map[rel] = f

    file_to_views: dict[str, list[str]] = {f: [] for f in changed_files}
    for node in graph.nodes.values():
        if node.kind != "view" or not node.source_file:
            continue
        src = Path(node.source_file).as_posix()
        if src in relative_map:
            file_to_views[relative_map[src]].append(node.name)
    return file_to_views


def _find_bot_comment(pr: str) -> str | None:
    """Return the id of the existing strata-bot comment on a PR, if any."""
    result = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{{owner}}/{{repo}}/issues/{pr}/comments",
            "--jq",
            f'.[] | select(.body | startswith("{BOT_MARKER}")) | .id',
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    ids = result.stdout.split()
    return ids[-1] if ids else None


def _post_or_update_comment(pr: str, body: str) -> int:
    """Upsert the strata-bot comment: edit the existing one or post a new one."""
    body = f"{BOT_MARKER}\n{body}"
    comment_id = _find_bot_comment(pr)
    if comment_id:
        endpoint = f"repos/{{owner}}/{{repo}}/issues/comments/{comment_id}"
        method = "PATCH"
    else:
        endpoint = f"repos/{{owner}}/{{repo}}/issues/{pr}/comments"
        method = "POST"
    result = subprocess.run(
        ["gh", "api", "--method", method, endpoint, "-f", f"body={body}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return result.returncode
    action = "Updated" if comment_id else "Posted"
    print(f"{action} Strata analysis on PR #{pr}")
    return 0


def _run_conductor_validation() -> str:
    """Run strata validate, ignoring the exit code, and return the formatted text."""
    try:
        result = subprocess.run(
            ["strata", "validate", "--check-replay"], capture_output=True, text=True, check=False
        )
        output = result.stdout.strip() or result.stderr.strip()
        return f"\n### Conductor Validation\n```text\n{output}\n```\n"
    except FileNotFoundError:
        return "\n### Conductor Validation\n```text\nstrata command not found\n```\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Path to LookML repo root")
    parser.add_argument(
        "--changed",
        nargs="+",
        required=True,
        metavar="FILE",
        help="Changed file paths (from git diff)",
    )
    parser.add_argument("--usage-fixture", help="Optional usage facts JSON for L1 enrichment")
    parser.add_argument("--schema-fixture", help="Optional schema facts JSON for L1 enrichment")
    parser.add_argument("--pr", help="PR number to comment on (omit with --dry-run)")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print comment to stdout instead of posting"
    )
    args = parser.parse_args()

    lkml_files = [f for f in args.changed if f.endswith(".lkml")]

    if lkml_files:
        graph = build_graph(args.repo, args.usage_fixture, args.schema_fixture)
        file_to_views = _files_to_views(graph, lkml_files)

        changed_views = sorted({v for views in file_to_views.values() for v in views})
        scope = strata_validation_scope(graph, [f"view:{v}" for v in changed_views])
        dead_code = strata_dead_code_register(graph)

        comment = build_pr_comment(lkml_files, file_to_views, scope, dead_code)
    else:
        comment = "## Strata Analysis\n\nNo LookML files modified in this PR.\n"

    comment += _run_conductor_validation()

    if args.dry_run:
        print(comment)
        return 0

    if not args.pr:
        parser.error("--pr is required when not using --dry-run")

    return _post_or_update_comment(str(args.pr), comment)


if __name__ == "__main__":
    raise SystemExit(main())
