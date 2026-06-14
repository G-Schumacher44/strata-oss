"""Strata CLI — unified command group."""

from __future__ import annotations

import click

from strata.cli.auth import auth
from strata.cli.bootstrap import bootstrap
from strata.cli.build_ir import build_ir
from strata.cli.chart import chart
from strata.cli.check import check
from strata.cli.conductor import conductor
from strata.cli.dashboard import dashboard
from strata.cli.generate_schema import generate_schema
from strata.cli.lint import lint
from strata.cli.mcp import mcp
from strata.cli.outputs import outputs
from strata.cli.query import query
from strata.cli.skill import skill
from strata.cli.validate import validate


@click.group()
@click.version_option(package_name="strata")
def strata_cli() -> None:
    """Strata BI Agentic Toolkit — govern, analyze, and visualize LookML repos."""


@strata_cli.command("clean")
@click.option("--repo", default=None, help="Repo path — also removes strata_ir.db inside it")
def clean(repo: str | None) -> None:
    """Remove generated artifacts from the working directory.

    Deletes: output/ directory, strata_ir.db cache files, and __pycache__ dirs.
    Safe to run at any time — re-run `strata outputs` or `strata build` to regenerate.
    """
    import shutil
    from pathlib import Path

    removed = []

    out_dir = Path("output")
    if out_dir.exists():
        shutil.rmtree(out_dir)
        removed.append("output/")

    search_root = Path(repo).expanduser().resolve() if repo else Path.cwd()
    for db in search_root.rglob("strata_ir.db"):
        db.unlink()
        removed.append(str(db))

    for cache in Path(".").rglob("__pycache__"):
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
strata_cli.add_command(dashboard)
strata_cli.add_command(lint)
strata_cli.add_command(query)
strata_cli.add_command(skill)
strata_cli.add_command(build_ir, name="build")
strata_cli.add_command(validate)
strata_cli.add_command(generate_schema)

if __name__ == "__main__":
    strata_cli()
