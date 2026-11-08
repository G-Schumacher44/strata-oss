"""strata bootstrap — drop full governance into any repo.

Plan first, ask second, write last: every input (flags or prompts) is gathered before the
first byte is written, and the writes are applied all-or-nothing (see `bootstrap.plan`).
"""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any

import click

from strata_lookml.bootstrap.plan import (
    FileOp,
    apply_plan,
    plan_template_write,
    render_mcp_client_config,
    render_template,
    resolve_fixture,
    report_ops,
)
from strata_lookml.cli.conductor import plan_conductor_init


@click.command("bootstrap")
@click.option("--repo", default=".", show_default=True, help="Target repo path")
@click.option("--no-git", is_flag=True, help="Skip .gitignore update")
@click.option("--no-conductor", is_flag=True, help="Skip conductor/ setup")
@click.option("--no-mcp", is_flag=True, help="Skip .mcp.json / .cursor/mcp.json")
@click.option("--force", is_flag=True, help="Overwrite existing files")
@click.option(
    "--yes", "-y", is_flag=True, help="Non-interactive: take flags and defaults, no prompts"
)
@click.option("--bq-project", default=None, help="BigQuery project for ~/.strata/config.json")
@click.option(
    "--cost-threshold-gb",
    type=float,
    default=None,
    help="BQ dry-run cost hard stop in GB for ~/.strata/config.json",
)
@click.option(
    "--set-default-repo/--no-set-default-repo",
    default=None,
    help="Write this repo as repo_path in ~/.strata/config.json "
    "(default with --yes: only if no config exists yet)",
)
@click.option(
    "--usage-fixture",
    type=click.Path(path_type=Path),
    default=None,
    envvar="STRATA_USAGE_FIXTURE",
    show_envvar=True,
    help="usage_facts.json to wire into .mcp.json as STRATA_USAGE_FIXTURE",
)
@click.option(
    "--schema-fixture",
    type=click.Path(path_type=Path),
    default=None,
    envvar="STRATA_SCHEMA_FIXTURE",
    show_envvar=True,
    help="schema_facts.json to wire into .mcp.json as STRATA_SCHEMA_FIXTURE",
)
@click.option("--dry-run", is_flag=True, help="Print the plan, write nothing (implies no prompts)")
def bootstrap(
    repo: str,
    no_git: bool,
    no_conductor: bool,
    no_mcp: bool,
    force: bool,
    yes: bool,
    bq_project: str | None,
    cost_threshold_gb: float | None,
    set_default_repo: bool | None,
    usage_fixture: Path | None,
    schema_fixture: Path | None,
    dry_run: bool,
) -> None:
    """Drop full Strata governance into a repo and prep the environment.

    Prompts on a terminal; pass --yes (with flags for the values) to run
    unattended, or --dry-run to see the plan first. Writes are all-or-nothing.

    \b
    $ strata bootstrap --repo . --yes --bq-project my-proj --usage-fixture usage_facts.json
    """
    target = Path(repo).expanduser().resolve()
    if not target.exists():
        raise click.ClickException(f"Repo path does not exist: {target}")

    interactive = not (yes or dry_run)
    if interactive and not sys.stdin.isatty():
        raise click.UsageError(
            "bootstrap needs a terminal to prompt on; pass --yes to run non-interactively "
            "(optionally with --bq-project, --cost-threshold-gb, --set-default-repo). "
            "Nothing was written."
        )
    for flag, fixture in (("--usage-fixture", usage_fixture), ("--schema-fixture", schema_fixture)):
        if fixture is not None and not fixture.expanduser().is_file():
            raise click.UsageError(f"{flag}: not a file: {fixture}")
    usage = resolve_fixture(usage_fixture)
    schema = resolve_fixture(schema_fixture)

    # Gather every input before anything is written.
    config_path = Path.home() / ".strata" / "config.json"
    new_config = _gather_config(
        config_path, target, interactive, bq_project, cost_threshold_gb, set_default_repo
    )

    ops = plan_bootstrap(target, no_git, no_conductor, no_mcp, force, usage, schema)
    if new_config is not None:
        ops.append(
            FileOp(
                "write",
                config_path,
                json.dumps(new_config, indent=2),
                label=f"wrote: {config_path}",
            )
        )

    click.secho(f"Bootstrapping Strata governance into: {target}", bold=True)
    click.echo("")
    if dry_run:
        report_ops(ops, dry_run=True)
        click.echo("")
        click.echo("Dry run: nothing written.")
        return
    apply_plan(ops)
    report_ops(ops)

    click.echo("")
    click.secho("Bootstrap complete.", fg="green")
    click.echo("Next: strata mcp validate")


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def plan_bootstrap(
    target: Path,
    no_git: bool,
    no_conductor: bool,
    no_mcp: bool,
    force: bool,
    usage: Path | None = None,
    schema: Path | None = None,
) -> list[FileOp]:
    subs = {"{{PROJECT_NAME}}": target.name}
    ops: list[FileOp] = []
    if not no_git:
        ops.append(_plan_gitignore(target))
    ops.append(plan_template_write(target / "AGENTS.md", "AGENTS.md", subs, force, "AGENTS.md"))
    ops.append(plan_template_write(target / "CLAUDE.md", "CLAUDE.md", subs, force, "CLAUDE.md"))
    if not no_conductor:
        ops.extend(plan_conductor_init(target, force))
    if not no_mcp:
        for rel, client in ((".mcp.json", "claude"), (".cursor/mcp.json", "cursor")):
            dest = target / rel
            if dest.exists() and not force:
                ops.append(FileOp("skip", dest, label=f"skip (exists): {rel}  (use --force)"))
            else:
                content = render_mcp_client_config(target, usage, schema, client)
                ops.append(FileOp("write", dest, content, label=f"wrote: {rel}"))
    return ops


def _plan_gitignore(target: Path) -> FileOp:
    gitignore = target / ".gitignore"
    block = render_template("gitignore.append")
    if not gitignore.exists():
        return FileOp("write", gitignore, block, label="wrote: .gitignore")
    existing = gitignore.read_text(encoding="utf-8")
    if "# Strata" in existing:
        return FileOp("skip", gitignore, label="skip (already present): .gitignore Strata block")
    return FileOp(
        "write", gitignore, existing.rstrip() + "\n\n" + block, label="appended: .gitignore"
    )


# ---------------------------------------------------------------------------
# Config inputs
# ---------------------------------------------------------------------------


def _gather_config(
    config_path: Path,
    target: Path,
    interactive: bool,
    bq_project: str | None,
    cost_threshold_gb: float | None,
    set_default_repo: bool | None,
) -> dict[str, Any] | None:
    """Resolve the new ~/.strata/config.json contents, or None when it should stay as is."""
    existing: dict[str, Any] = {}
    have_file = config_path.exists()
    if have_file:
        with contextlib.suppress(json.JSONDecodeError, OSError):
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded

    cfg = dict(existing)
    if interactive:
        if have_file:
            click.echo("\n  ~/.strata/config.json already exists:")
            click.echo(f"    repo_path:        {existing.get('repo_path', '(not set)')}")
            click.echo(f"    bq_project:       {existing.get('bq_project', '(not set)')}")
            click.echo(
                f"    cost_threshold_gb:{existing.get('cost_threshold_gb', '(default: 100)')}"
            )
            if not click.confirm("  Update it?", default=False):
                click.echo("  Kept existing config.")
                return None
        click.echo("")
        if set_default_repo is None:
            cfg["repo_path"] = _prompt_repo_path(
                existing.get("repo_path") or str(target), str(target)
            )
        elif set_default_repo:
            cfg["repo_path"] = str(target)
        if bq_project is None:
            bq_project = click.prompt(
                "  BigQuery project (for 2-part table names; leave blank to use gcloud default)",
                default=existing.get("bq_project", ""),
                show_default=False,
            )
        if cost_threshold_gb is None:
            cost_threshold_gb = float(
                click.prompt(
                    "  BQ query cost threshold GB (dry-run hard stop)",
                    default=existing.get("cost_threshold_gb", 100),
                    show_default=True,
                )
            )
    else:
        if set_default_repo is None:
            set_default_repo = not have_file
        if set_default_repo:
            cfg["repo_path"] = str(target)
        if not have_file and cost_threshold_gb is None:
            cost_threshold_gb = 100.0

    if bq_project:
        cfg["bq_project"] = bq_project
    if cost_threshold_gb is not None:
        cfg["cost_threshold_gb"] = float(cost_threshold_gb)
    if cfg == existing and have_file:
        return None
    return cfg or None


def _prompt_repo_path(default_repo: str, target: str) -> str:
    """Prompt for a LookML repo path, re-prompting if it does not exist.

    Prevents a typo (or a mis-piped keystroke) from silently becoming a broken
    global repo_path that only surfaces later as a cryptic `strata mcp validate` error.
    """
    while True:
        repo_path = click.prompt("  LookML repo path", default=default_repo)
        if Path(repo_path).expanduser().is_dir():
            return repo_path
        click.secho(f"  ⚠ path does not exist: {repo_path}", fg="yellow")
        if click.confirm("  Save it anyway?", default=False):
            return repo_path
        default_repo = target
