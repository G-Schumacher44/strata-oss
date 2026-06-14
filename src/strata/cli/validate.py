"""strata validate — Conductor spine and replay facts validation."""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
import sys
from datetime import UTC
from pathlib import Path

import click


@click.command("validate")
@click.option(
    "--project-root",
    default=None,
    envvar="CONDUCTOR_PROJECT_ROOT",
    help="Project root to validate (defaults to repo root)",
)
@click.option("--check-replay", is_flag=True, help="Also validate tests/fixtures/replay_facts.json")
@click.option("--replay", default=None, help="Path to replay facts JSON (used with --check-replay)")
def validate(project_root: str | None, check_replay: bool, replay: str | None) -> None:
    """Validate the Conductor spine and (optionally) replay L1 facts.

    Checks: required files present, handoff-log format, active slice acceptance
    criteria, commit hash reachable in git, CI workflow stub present.

    Exits 0 if all checks pass (warnings allowed), 1 if any fail.

    \b
    strata validate
    strata validate --check-replay
    strata validate --project-root /path/to/my-project
    """
    repo_root = Path(__file__).resolve().parents[3]
    project = Path(project_root).expanduser().resolve() if project_root else repo_root
    project_deployed = project.exists()

    results: list[dict] = []

    def check(name: str, fn):
        try:
            status, message, detail = fn()
            results.append({"name": name, "status": status, "message": message, "detail": detail})
        except Exception as exc:
            results.append({"name": name, "status": "fail", "message": str(exc), "detail": None})

    # ── Spine structure ───────────────────────────────────────────────────
    check(
        "project/ directory",
        lambda: (
            ("pass", "", None)
            if project_deployed
            else ("warn", "not found — set CONDUCTOR_PROJECT_ROOT or scaffold first", None)
        ),
    )

    for rel in ["AGENTS.md", "conductor/index.md", "conductor/handoff-log.md"]:
        check(
            f"project/{rel}",
            lambda p=rel: (
                ("skip", "project/ not deployed", None)
                if not project_deployed
                else ("pass", "", None)
                if (project / p).exists()
                else ("fail", "missing — scaffold incomplete", None)
            ),
        )

    # ── Handoff format ────────────────────────────────────────────────────
    def check_handoff():
        if not project_deployed:
            return "skip", "project/ not deployed", None
        f = project / "conductor" / "handoff-log.md"
        if not f.exists():
            return "fail", "missing", None
        content = re.sub(r"<!--.*?-->", "", f.read_text(), flags=re.DOTALL).strip()
        if len(content) < 50:
            return "warn", "appears empty — agent may not have written the handoff yet", None
        missing = []
        if "Commit:" not in content:
            missing.append("Commit:")
        if "Exact Next Steps" not in content:
            missing.append("Exact Next Steps")
        if missing:
            return "warn", f"required fields missing: {', '.join(missing)}", None
        return "pass", "", None

    check("handoff-log.md written", check_handoff)

    def check_handoff_ttl():
        if not project_deployed:
            return "skip", "project/ not deployed", None
        f = project / "conductor" / "handoff-log.md"
        if not f.exists():
            return "skip", "handoff-log.md missing", None
        content = re.sub(r"<!--.*?-->", "", f.read_text(), flags=re.DOTALL)
        m = re.search(r"##\s+Date:\s*(\d{4}-\d{2}-\d{2})", content)
        if not m:
            return "warn", "no Date: field found — cannot check TTL", None
        import datetime

        try:
            handoff_date = datetime.date.fromisoformat(m.group(1))
        except ValueError:
            return "warn", f"Date: {m.group(1)!r} is not a valid ISO date", None
        age_days = (datetime.date.today() - handoff_date).days
        ttl = int(os.environ.get("STRATA_HANDOFF_TTL_DAYS", "14"))
        if age_days > ttl:
            return (
                "warn",
                f"handoff is {age_days}d old (TTL={ttl}d) — consider refreshing before continuing",
                None,
            )
        return "pass", f"{age_days}d old", None

    check("Handoff TTL", check_handoff_ttl)

    def check_commit_hash():
        if not project_deployed:
            return "skip", "project/ not deployed", None
        f = project / "conductor" / "handoff-log.md"
        if not f.exists():
            return "skip", "handoff-log.md missing", None
        content = re.sub(r"<!--.*?-->", "", f.read_text(), flags=re.DOTALL)
        m = re.search(r"Commit:\s*([0-9a-f]{7,40})", content, re.IGNORECASE)
        if not m:
            return "warn", "no commit hash found in Commit: field", None
        commit = m.group(1)
        try:
            subprocess.check_output(
                ["git", "cat-file", "-e", commit],
                cwd=repo_root,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            return (
                "fail",
                f"Commit: {commit} does not exist in git — handoff may be hallucinated",
                None,
            )
        try:
            log = subprocess.check_output(
                ["git", "log", "--oneline", "--ancestry-path", f"{commit}^..HEAD"],
                cwd=repo_root,
                text=True,
                stderr=subprocess.DEVNULL,
            )
            if commit[:7] not in log:
                return "warn", f"Commit: {commit} exists but is not reachable from HEAD", None
        except Exception:
            pass
        return "pass", commit, None

    check("Handoff commit hash is real", check_commit_hash)

    # ── CI workflow stub ──────────────────────────────────────────────────
    def check_ci_stub():
        if not project_deployed:
            return "skip", "project/ not deployed", None
        workflows = project / ".github" / "workflows"
        if not workflows.exists() or not any(workflows.iterdir()):
            return "warn", "no .github/workflows — stub recommended", None
        files = [f.name for f in workflows.iterdir()]
        return "pass", ", ".join(files), None

    check("CI workflow stub", check_ci_stub)

    # ── Active slice + acceptance criteria ────────────────────────────────
    def get_active_slice_rel():
        index = project / "conductor" / "index.md"
        if not index.exists():
            return None
        m = re.search(r"Active slice:\s*(.+)", index.read_text(), re.IGNORECASE)
        return m.group(1).strip() if m else None

    def parse_acceptance_criteria(content):
        m = re.search(r"##\s+Acceptance Criteria(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if not m:
            return []
        items = []
        for line in m.group(1).splitlines():
            ticked = re.match(r"[-*]\s+\[x\]\s+(.+)", line, re.IGNORECASE)
            open_ = re.match(r"[-*]\s+\[ \]\s+(.+)", line, re.IGNORECASE)
            if ticked:
                items.append((True, ticked.group(1).strip()))
            elif open_:
                items.append((False, open_.group(1).strip()))
        return items

    active_slice_rel = get_active_slice_rel() if project_deployed else None

    def check_active_slice():
        if not project_deployed:
            return "skip", "project/ not deployed", None
        if not active_slice_rel:
            return "warn", "could not parse from conductor/index.md", None
        if active_slice_rel.lower().startswith("none"):
            return "pass", active_slice_rel, None
        if not (project / active_slice_rel).exists():
            return "fail", f"{active_slice_rel} not found", None
        return "pass", active_slice_rel, None

    check("Active slice file", check_active_slice)

    if (
        active_slice_rel
        and not active_slice_rel.lower().startswith("none")
        and (project / active_slice_rel).exists()
    ):
        criteria = parse_acceptance_criteria((project / active_slice_rel).read_text())
        if criteria:
            done = sum(1 for ticked, _ in criteria if ticked)
            total = len(criteria)
            lines = "\n".join(f"       {'[x]' if t else '[ ]'} {text}" for t, text in criteria)
            results.append(
                {
                    "name": f"Acceptance criteria  {done}/{total} checked",
                    "status": "pass" if done == total else "fail",
                    "message": "" if done == total else "unchecked items block handoff",
                    "detail": lines,
                }
            )
        else:
            results.append(
                {
                    "name": "Acceptance criteria",
                    "status": "warn",
                    "message": "no checklist items found — add an Acceptance Criteria section",
                    "detail": None,
                }
            )

    # ── Git branch ────────────────────────────────────────────────────────
    def check_branch():
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            return "skip", "CI environment", None
        try:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=repo_root,
                text=True,
            ).strip()
            if not branch:
                return "warn", "detached HEAD", None
            if branch == "main":
                return "fail", f"on {branch} — commits should go on dev or a feature branch", None
            return "pass", branch, None
        except Exception:
            return "warn", "could not determine branch", None

    check("Git branch is a feature branch", check_branch)

    # ── Replay facts (optional) ───────────────────────────────────────────
    if check_replay:
        replay_path = (
            Path(replay).expanduser().resolve()
            if replay
            else (repo_root / "tests" / "fixtures" / "replay_facts.json")
        )

        def check_replay_facts():
            if not replay_path.exists():
                return "fail", f"replay facts not found: {replay_path}", None
            from strata.l1.provider import UsageFacts
            from strata.l1.replay import ReplayLookerUsageProvider

            facts = UsageFacts.from_provider(ReplayLookerUsageProvider(str(replay_path)))
            count = len(facts.explore_usage)
            if count == 0:
                return "fail", "replay has no explore usage rows after normalization", None
            return "pass", f"{count} explore usage rows", None

        check("Replay facts valid", check_replay_facts)

    # ── Verdict log (append-only telemetry) ──────────────────────────────
    def _append_verdict_log(
        failed_count: int, passed_count: int, warned_count: int, skipped_count: int
    ) -> None:
        from datetime import datetime

        env_path = os.environ.get("CONDUCTOR_VALIDATION_LOG")
        log_path = Path(env_path) if env_path else (project / "conductor" / ".validation-log")
        status = "reject" if failed_count > 0 else "pass"
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        row = f"{ts},{status},{passed_count},{warned_count},{failed_count},{skipped_count}\n"
        new_file = not log_path.exists()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            if new_file:
                fh.write("timestamp,status,passed,warnings,failed,skipped\n")
            fh.write(row)

    # ── Report ────────────────────────────────────────────────────────────
    passed = sum(1 for r in results if r["status"] == "pass")
    warned = sum(1 for r in results if r["status"] == "warn")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skip")

    icons = {"pass": "✓", "warn": "~", "fail": "✗", "skip": "-"}
    hr = "─" * 52
    click.echo(f"\nConductor Spine Validation\n{hr}")
    for r in results:
        icon = icons.get(r["status"], "?")
        suffix = f"  — {r['message']}" if r["message"] else ""
        click.echo(f"  {icon}  {r['name']}{suffix}")
        if r["detail"]:
            click.echo(r["detail"])
    click.echo(hr)
    click.echo(
        f"  {passed} passed  |  {warned} warnings  |  {failed} failed  |  {skipped} skipped\n"
    )

    with contextlib.suppress(Exception):
        _append_verdict_log(failed, passed, warned, skipped)

    sys.exit(1 if failed > 0 else 0)
