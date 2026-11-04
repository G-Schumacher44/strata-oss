"""strata conductor — slice-based workflow management."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import click


@click.group()
def conductor() -> None:
    """Slice-based workflow system for governing AI agent sessions.

    Conductor gives agents a structured execution contract: read the active
    slice, do bounded work, write a handoff. Keeps context spend proportional
    to risk across long-running LookML governance projects.
    """


@conductor.command("init")
@click.option("--repo", default=".", show_default=True, help="Target repo path")
@click.option("--force", is_flag=True, help="Overwrite existing conductor/ files")
def conductor_init(repo: str, force: bool) -> None:
    """Set up the conductor/ directory with modes, templates, and handoff log."""
    target = Path(repo).expanduser().resolve()
    conductor_dir = target / "conductor"
    templates_dir = conductor_dir / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    (conductor_dir / "review").mkdir(exist_ok=True)
    (conductor_dir / "archive").mkdir(exist_ok=True)

    tpl_root = Path(__file__).resolve().parent.parent / "bootstrap" / "templates"
    today = date.today().isoformat()
    project = target.name

    def _write(dest: Path, src_name: str, subs: dict[str, str] | None = None) -> None:
        src = tpl_root / src_name
        if dest.exists() and not force:
            click.echo(f"  skip (exists): {dest.relative_to(target)}")
            return
        content = src.read_text(encoding="utf-8")
        if subs:
            for k, v in subs.items():
                content = content.replace(k, v)
        dest.write_text(content, encoding="utf-8")
        click.secho(f"  wrote: {dest.relative_to(target)}", fg="green")

    subs = {"{{PROJECT_NAME}}": project, "{{DATE}}": today}

    _write(conductor_dir / "CONDUCTOR_MODES.md", "conductor_CONDUCTOR_MODES.md")
    _write(conductor_dir / "README.md", "conductor_README.md", subs)
    _write(conductor_dir / "index.md", "conductor_index.md", subs)
    _write(conductor_dir / "handoff-log.md", "conductor_handoff_log.md", subs)
    _write(conductor_dir / "handoff-archive.md", "conductor_handoff_archive.md", subs)
    _write(
        conductor_dir / "templates" / "CONDUCTOR_SLICE_TEMPLATE.md", "conductor_slice_template.md"
    )
    _write(
        conductor_dir / "templates" / "CONDUCTOR_STARTER_PROMPT_TEMPLATE.md",
        "conductor_starter_prompt.md",
        subs,
    )

    click.secho(f"\nconductor/ initialised in {target}", fg="green")
    click.echo("Next: strata conductor new-slice 'My first slice'")


@conductor.command("new-slice")
@click.argument("title")
@click.option("--repo", default=".", show_default=True, help="Target repo path")
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
@click.option("--repo", default=".", show_default=True, help="Target repo path")
def conductor_status(repo: str) -> None:
    """Show the active slice, execution mode, and next steps from handoff-log."""
    target = Path(repo).expanduser().resolve()
    conductor_dir = target / "conductor"

    if not conductor_dir.exists():
        raise click.ClickException("No conductor/ directory found. Run: strata conductor init")

    # Read index for active slice
    index_path = conductor_dir / "index.md"
    active_slice_file: Path | None = None
    if index_path.exists():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            m = re.search(r"[Aa]ctive [Ss]lice[:\s]+conductor/(slice-[^\s]+\.md)", line)
            if m:
                active_slice_file = conductor_dir / m.group(1).replace("conductor/", "")
                break

    click.secho("=== Conductor Status ===", bold=True)

    if active_slice_file and active_slice_file.exists():
        lines = active_slice_file.read_text(encoding="utf-8").splitlines()
        title_line = lines[0].lstrip("# ").strip() if lines else active_slice_file.name
        status = next(
            (line.split(":", 1)[1].strip() for line in lines if line.startswith("Status:")),
            "unknown",
        )
        mode_line = next((line for line in lines if "conductor_mode:" in line), None)
        mode = mode_line.split(":", 1)[1].strip() if mode_line else "unknown"
        click.echo(f"Active slice : {active_slice_file.name}")
        click.echo(f"Title        : {title_line}")
        click.echo(f"Status       : {status}")
        click.echo(f"Mode         : {mode}")
    else:
        click.secho("No active slice found in conductor/index.md", fg="yellow")

    # Read latest handoff block
    handoff_path = conductor_dir / "handoff-log.md"
    if handoff_path.exists():
        text = handoff_path.read_text(encoding="utf-8")
        blocks = [b.strip() for b in text.split("##") if b.strip()]
        if blocks:
            latest = "##" + blocks[1] if len(blocks) > 1 else "##" + blocks[0]
            next_steps = next(
                (
                    line.split(":", 1)[1].strip()
                    for line in latest.splitlines()
                    if line.startswith("Exact Next Steps")
                ),
                None,
            )
            click.echo("")
            click.secho("Latest handoff:", bold=True)
            click.echo(latest[:600] + ("…" if len(latest) > 600 else ""))
            if next_steps:
                click.echo("")
                click.secho(f"Next steps: {next_steps}", fg="cyan")
    else:
        click.secho("No handoff-log.md found.", fg="yellow")
