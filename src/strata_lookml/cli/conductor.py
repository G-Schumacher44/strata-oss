"""strata conductor — slice-based workflow management."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import click

from strata_lookml.bootstrap.plan import FileOp, apply_plan, plan_template_write, report_ops
from strata_lookml.conductor_state import read_status


@click.group()
def conductor() -> None:
    """Slice-based workflow system for governing AI agent sessions.

    Conductor gives agents a structured execution contract: read the active
    slice, do bounded work, write a handoff. Keeps context spend proportional
    to risk across long-running LookML governance projects.
    """


def plan_conductor_init(target: Path, force: bool = False) -> list[FileOp]:
    """Plan the `conductor/` scaffold under `target` without writing anything."""
    conductor_dir = target / "conductor"
    subs = {"{{PROJECT_NAME}}": target.name, "{{DATE}}": date.today().isoformat()}

    def _op(rel: str, template: str, with_subs: bool = True) -> FileOp:
        return plan_template_write(
            conductor_dir / rel, template, subs if with_subs else None, force, f"conductor/{rel}"
        )

    return [
        FileOp("mkdir", conductor_dir / "templates"),
        FileOp("mkdir", conductor_dir / "review"),
        FileOp("mkdir", conductor_dir / "archive"),
        _op("CONDUCTOR_MODES.md", "conductor_CONDUCTOR_MODES.md", with_subs=False),
        _op("README.md", "conductor_README.md"),
        _op("index.md", "conductor_index.md"),
        _op("handoff-log.md", "conductor_handoff_log.md"),
        _op("handoff-archive.md", "conductor_handoff_archive.md"),
        _op(
            "templates/CONDUCTOR_SLICE_TEMPLATE.md",
            "conductor_slice_template.md",
            with_subs=False,
        ),
        _op("templates/CONDUCTOR_STARTER_PROMPT_TEMPLATE.md", "conductor_starter_prompt.md"),
    ]


@conductor.command("init")
@click.option(
    "--repo",
    default=".",
    show_default=True,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="Target repo path",
)
@click.option("--force", is_flag=True, help="Overwrite existing conductor/ files")
def conductor_init(repo: str, force: bool) -> None:
    """Set up the conductor/ directory with modes, templates, and handoff log."""
    target = Path(repo).expanduser().resolve()
    ops = plan_conductor_init(target, force)
    apply_plan(ops)
    report_ops(ops)

    click.secho(f"\nconductor/ initialised in {target}", fg="green")
    click.echo("Next: strata conductor new-slice 'My first slice'")


@conductor.command("new-slice")
@click.argument("title")
@click.option(
    "--repo",
    default=".",
    show_default=True,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="Target repo path",
)
@click.option(
    "--mode",
    default="slice",
    type=click.Choice(["patch", "slice", "full", "audit"]),
    help="patch=one-file fix, slice=planned feature, full=cross-layer change, audit=review only",
    show_default=True,
)
@click.option(
    "--budget",
    default="medium",
    type=click.Choice(["low", "medium", "high"]),
    help="Expected context spend for this slice",
    show_default=True,
)
def conductor_new_slice(title: str, repo: str, mode: str, budget: str) -> None:
    """Create the next numbered slice file from the slice template.

    Auto-numbers from existing slices (slice-01, slice-02, ...).
    After creation, update conductor/index.md to set it as the active slice.
    """
    target = Path(repo).expanduser().resolve()
    conductor_dir = target / "conductor"

    if not conductor_dir.exists():
        raise click.ClickException("No conductor/ directory found. Run: strata conductor init")

    # Find next slice number
    existing = list(conductor_dir.glob("slice-*.md"))
    nums = []
    for f in existing:
        m = re.match(r"slice-(\d+)", f.stem)
        if m:
            nums.append(int(m.group(1)))
    nn = (max(nums) + 1) if nums else 1
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    filename = f"slice-{nn:02d}-{slug}.md"
    dest = conductor_dir / filename

    today = date.today().isoformat()
    content = (
        f"# Slice {nn:02d}: {title}\n\n"
        f"Date: {today}\n"
        f"Status: queued\n"
        f"Phase: TBD\n"
        f"Depends: none\n\n"
        f"```yaml\n"
        f"conductor_mode: {mode}\n"
        f"context_budget: {budget}\n"
        f"handoff_required: true\n"
        f"stable_tag_required: false\n"
        f"```\n\n"
        f"## Objective\n\n"
        f"One paragraph. What problem does this slice solve? Why now?\n\n"
        f"## Scope\n\n"
        f"Which layer(s) does this touch?\n\n"
        f"## Implementation Order\n\n"
        f"1.\n2.\n3.\n\n"
        f"## The Hard Constraint (if any)\n\n"
        f"Call out the make-or-break correctness requirement explicitly.\n\n"
        f"## Acceptance Criteria\n\n"
        f"- [ ] Gate 1\n"
        f"- [ ] Gate 2\n"
        f"- [ ] Tests pass\n"
        f"- [ ] `conductor/handoff-log.md` — STABLE entry with Commit: hash\n"
    )
    dest.write_text(content, encoding="utf-8")
    click.secho(f"Created: conductor/{filename}", fg="green")
    click.echo(f"Update conductor/index.md → Active Slice: conductor/{filename}")


@conductor.command("status")
@click.option(
    "--repo",
    default=".",
    show_default=True,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="Target repo path",
)
def conductor_status(repo: str) -> None:
    """Show the active slice, execution mode, and next steps from handoff-log."""
    target = Path(repo).expanduser().resolve()
    conductor_dir = target / "conductor"

    if not conductor_dir.exists():
        raise click.ClickException("No conductor/ directory found. Run: strata conductor init")

    state = read_status(conductor_dir)

    click.secho("=== Conductor Status ===", bold=True)

    if state["active_slice"]:
        click.echo(f"Active slice : {state['active_slice']}")
        click.echo(f"Title        : {state['title'] or 'unknown'}")
        click.echo(f"Status       : {state['status'] or 'unknown'}")
        click.echo(f"Mode         : {state['mode'] or 'unknown'}")
    else:
        click.secho("No active slice found in conductor/index.md", fg="yellow")

    if state["latest_handoff"]:
        latest = state["latest_handoff"]
        click.echo("")
        click.secho("Latest handoff:", bold=True)
        click.echo(latest[:600] + ("…" if len(latest) > 600 else ""))
        if state["next_steps"]:
            click.echo("")
            click.secho(f"Next steps: {state['next_steps']}", fg="cyan")
    elif not (conductor_dir / "handoff-log.md").exists():
        click.secho("No handoff-log.md found.", fg="yellow")
