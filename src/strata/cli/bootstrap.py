"""strata bootstrap — drop full governance into any repo."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import click


@click.command("bootstrap")
@click.option("--repo", default=".", show_default=True, help="Target repo path")
@click.option("--no-git", is_flag=True, help="Skip .gitignore update")
@click.option("--no-conductor", is_flag=True, help="Skip conductor/ setup")
@click.option("--no-mcp", is_flag=True, help="Skip .mcp.json / .cursor/mcp.json")
@click.option("--force", is_flag=True, help="Overwrite existing files")
def bootstrap(
    repo: str,
    no_git: bool,
    no_conductor: bool,
    no_mcp: bool,
    force: bool,
) -> None:
    """Drop full Strata governance into a repo and prep the environment."""
    target = Path(repo).expanduser().resolve()
    if not target.exists():
        raise click.ClickException(f"Repo path does not exist: {target}")

    tpl_root = Path(__file__).resolve().parent.parent / "bootstrap" / "templates"
    project = target.name

    click.secho(f"Bootstrapping Strata governance into: {target}", bold=True)
    click.echo("")

    # --- .gitignore ---
    if not no_git:
        _append_gitignore(target, tpl_root)

    # --- AGENTS.md ---
    _write_file(
        target / "AGENTS.md",
        tpl_root / "AGENTS.md",
        subs={"{{PROJECT_NAME}}": project},
        force=force,
    )

    # --- CLAUDE.md ---
    _write_file(
        target / "CLAUDE.md",
        tpl_root / "CLAUDE.md",
        subs={"{{PROJECT_NAME}}": project},
        force=force,
    )

    # --- conductor/ ---
    if not no_conductor:
        from click.testing import CliRunner

        from strata.cli.conductor import conductor_init

        runner = CliRunner()
        result = runner.invoke(
            conductor_init, ["--repo", str(target)] + (["--force"] if force else [])
        )
        click.echo(result.output.rstrip())

    # --- .mcp.json ---
    if not no_mcp:
        _write_mcp_configs(target, tpl_root, project, force)

    # --- ~/.strata/config.json ---
    _prompt_strata_config(target)

    click.echo("")
    click.secho("Bootstrap complete.", fg="green")
    click.echo("Next: strata mcp validate")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _append_gitignore(target: Path, tpl_root: Path) -> None:
    gitignore = target / ".gitignore"
    new_block = (tpl_root / "gitignore.append").read_text(encoding="utf-8")

    if gitignore.exists():
        existing = gitignore.read_text(encoding="utf-8")
        if "# Strata" in existing:
            click.echo("  skip (already present): .gitignore Strata block")
            return
        gitignore.write_text(existing.rstrip() + "\n\n" + new_block, encoding="utf-8")
        click.secho("  appended: .gitignore", fg="green")
    else:
        gitignore.write_text(new_block, encoding="utf-8")
        click.secho("  wrote: .gitignore", fg="green")


def _write_file(
    dest: Path,
    src: Path,
    subs: dict[str, str] | None = None,
    force: bool = False,
) -> None:
    if dest.exists() and not force:
        click.echo(f"  skip (exists): {dest.name}  (use --force to overwrite)")
        return
    content = src.read_text(encoding="utf-8")
    if subs:
        for k, v in subs.items():
            content = content.replace(k, v)
    dest.write_text(content, encoding="utf-8")
    click.secho(f"  wrote: {dest.name}", fg="green")


def _write_mcp_configs(target: Path, tpl_root: Path, project: str, force: bool) -> None:
    import sys

    strata_mcp_cmd = str(Path(sys.executable).parent / "strata-mcp")
    subs = {
        "{{PROJECT_NAME}}": project,
        "{{REPO_PATH}}": str(target),
        "{{STRATA_MCP_CMD}}": strata_mcp_cmd,
    }

    mcp_json = target / ".mcp.json"
    _write_file(mcp_json, tpl_root / "mcp.json", subs, force)

    cursor_dir = target / ".cursor"
    cursor_dir.mkdir(exist_ok=True)
    _write_file(cursor_dir / "mcp.json", tpl_root / "cursor_mcp.json", subs, force)


def _prompt_strata_config(target: Path) -> None:
    config_path = Path.home() / ".strata" / "config.json"

    existing: dict = {}
    if config_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            existing = json.loads(config_path.read_text(encoding="utf-8"))
        click.echo("\n  ~/.strata/config.json already exists:")
        click.echo(f"    repo_path:        {existing.get('repo_path', '(not set)')}")
        click.echo(f"    bq_project:       {existing.get('bq_project', '(not set)')}")
        click.echo(f"    cost_threshold_gb:{existing.get('cost_threshold_gb', '(default: 100)')}")
        if not click.confirm("  Update it?", default=False):
            click.echo("  Kept existing config.")
            return

    click.echo("")
    repo_path = _prompt_repo_path(existing.get("repo_path") or str(target), str(target))
    bq_project = click.prompt(
        "  BigQuery project (for 2-part table names; leave blank to use gcloud default)",
        default=existing.get("bq_project", ""),
        show_default=False,
    )
    cost_threshold = click.prompt(
        "  BQ query cost threshold GB (dry-run hard stop)",
        default=existing.get("cost_threshold_gb", 100),
        show_default=True,
    )

    cfg: dict = {"repo_path": repo_path}
    if bq_project:
        cfg["bq_project"] = bq_project
    cfg["cost_threshold_gb"] = float(cost_threshold)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    click.secho(f"  wrote: {config_path}", fg="green")


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
