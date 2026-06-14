"""strata lint — run ruff and mypy checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click


@click.command("lint")
@click.option(
    "--fix", is_flag=True, help="Attempt to fix violations automatically (ruff check --fix)"
)
@click.option("--format", "do_format", is_flag=True, help="Format the codebase (ruff format)")
@click.option(
    "--mypy", "do_mypy", is_flag=True, default=True, help="Run mypy type checks (default: true)"
)
@click.option(
    "--ruff", "do_ruff", is_flag=True, default=True, help="Run ruff lint checks (default: true)"
)
def lint(fix: bool, do_format: bool, do_mypy: bool, do_ruff: bool) -> None:
    """Run ruff and mypy checks on src/ and tests/.

    By default, runs both ruff check and mypy. Use --fix to auto-fix ruff issues.
    """
    root = Path.cwd()
    src = root / "src"
    tests = root / "tests"

    failed = False

    if do_ruff:
        click.secho("--- Ruff Check ---", bold=True)
        ruff_args = [sys.executable, "-m", "ruff", "check", str(src), str(tests)]
        if fix:
            ruff_args.append("--fix")

        res = subprocess.run(ruff_args)
        if res.returncode != 0:
            failed = True

    if do_format:
        click.secho("\n--- Ruff Format ---", bold=True)
        res = subprocess.run([sys.executable, "-m", "ruff", "format", str(src), str(tests)])
        if res.returncode != 0:
            failed = True

    if do_mypy:
        click.secho("\n--- Mypy Check ---", bold=True)
        res = subprocess.run(
            [sys.executable, "-m", "mypy", str(src / "strata"), "--ignore-missing-imports"]
        )
        if res.returncode != 0:
            failed = True

    if failed:
        click.secho("\nFAIL: Linting or type checks failed.", fg="red", bold=True)
        sys.exit(1)

    click.secho("\nPASS: Linting and type checks passed.", fg="green", bold=True)
