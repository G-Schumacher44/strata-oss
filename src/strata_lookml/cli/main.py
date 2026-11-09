"""Strata CLI — unified command group."""

from __future__ import annotations

import click

from strata_lookml.cli._contract import StrataGroup
from strata_lookml.cli.auth import auth
from strata_lookml.cli.bootstrap import bootstrap
from strata_lookml.cli.build_ir import build_ir
from strata_lookml.cli.chart import chart
from strata_lookml.cli.check import check
from strata_lookml.cli.conductor import conductor
from strata_lookml.cli.diff import diff
from strata_lookml.cli.generate_schema import generate_schema
from strata_lookml.cli.lint import lint
from strata_lookml.cli.mcp import mcp
from strata_lookml.cli.outputs import outputs
from strata_lookml.cli.query import query
from strata_lookml.cli.skill import skill
from strata_lookml.cli.validate import validate
from strata_lookml.cli.workbench import dashboard, workbench


@click.group(cls=StrataGroup)
@click.version_option(package_name="strata-lookml")
def strata_cli() -> None:
    """Strata BI Agentic Toolkit — govern, analyze, and visualize LookML repos."""


@strata_cli.command("clean")
@click.option(
    "--repo",
    default=None,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="Repo path — clean this repo's IR cache and sweep __pycache__ inside it instead of the cwd",
)
def clean(repo: str | None) -> None:
    """Remove generated artifacts.

    Deletes: output/ in the cwd (where `strata dashboard` writes by default); the repo's IR
    cache entry under ~/.strata/cache/ (--repo, else the cwd); and, under that repo, legacy
    strata_ir.db cache files (earlier releases wrote the cache there) and __pycache__ dirs. A cache at
    STRATA_CACHE_PATH / --cache is yours and is not touched. A repo's own output/ is never
    touched — Strata does not write there and cannot prove it owns it.
    Safe to run at any time — re-run `strata outputs` or `strata build` to regenerate.
    """
    import shutil
    from pathlib import Path

    from strata_lookml.config import LEGACY_CACHE_NAME, default_cache_path

    removed = []

    out_dir = Path("output")
    if out_dir.exists():
        shutil.rmtree(out_dir)
        removed.append("output/")

    search_root = Path(repo).expanduser().resolve() if repo else Path.cwd()
    cache_entry = default_cache_path(search_root)
    if cache_entry.exists():
        cache_entry.unlink()
        removed.append(str(cache_entry))

    for db in search_root.rglob(LEGACY_CACHE_NAME):
        db.unlink()
        removed.append(str(db))

    for cache in search_root.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    removed.append("__pycache__ dirs")

    if removed:
        click.echo("Removed: " + ", ".join(removed))
    else:
        click.echo("Nothing to clean.")


strata_cli.add_command(mcp)
strata_cli.add_command(chart)
strata_cli.add_command(auth)
strata_cli.add_command(conductor)
strata_cli.add_command(bootstrap)
strata_cli.add_command(check)
strata_cli.add_command(outputs)
strata_cli.add_command(workbench)
strata_cli.add_command(dashboard)
strata_cli.add_command(lint)
strata_cli.add_command(query)
strata_cli.add_command(skill)
strata_cli.add_command(build_ir, name="build")
strata_cli.add_command(validate)
strata_cli.add_command(diff)
strata_cli.add_command(generate_schema)

if __name__ == "__main__":
    strata_cli()
