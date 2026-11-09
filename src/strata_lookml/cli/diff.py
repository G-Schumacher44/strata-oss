"""strata diff — the findings a branch introduces or fixes, against the same usage evidence."""

from __future__ import annotations

import json
from pathlib import Path

import click

from strata_lookml.cli._contract import JsonCommand


@click.command("diff", cls=JsonCommand)
@click.argument("base_ref")
@click.argument("head_ref", required=False)
@click.option(
    "--repo",
    default=None,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="Path to the LookML git repo (defaults to cwd)",
)
@click.option(
    "--usage-fixture",
    default=None,
    envvar="STRATA_USAGE_FIXTURE",
    show_envvar=True,
    help="Production usage facts JSON, applied to both sides.",
)
@click.option(
    "--schema-fixture",
    default=None,
    envvar="STRATA_SCHEMA_FIXTURE",
    show_envvar=True,
    help="Schema facts JSON, applied to both sides.",
)
@click.option(
    "--fail-on-new", is_flag=True, help="Exit 1 if the head introduces any new finding (CI use)."
)
@click.option(
    "--json", "as_json", is_flag=True, help="Print {base, head, new, fixed, unchanged_count}"
)
def diff(
    base_ref: str,
    head_ref: str | None,
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
    fail_on_new: bool,
    as_json: bool,
) -> None:
    """Which findings does a branch introduce or fix? Exit 0, or 1 with --fail-on-new.

    Analyses BASE_REF and HEAD_REF (default: the working tree, uncommitted edits included) with
    the same usage and schema fixtures, so only the LookML differs; usage evidence is always the
    production data in the fixture. Findings are matched by id: new (only in head), fixed (only
    in base), unchanged. A ref is exported read-only with `git archive` into a temp dir: nothing
    is created in your repo (no worktree, ref or file). `git archive` leaves out submodule
    contents and honours `export-ignore` attributes.

    \b
    strata diff main --usage-fixture usage_facts.json
    strata diff origin/main feature --usage-fixture usage_facts.json --fail-on-new --json
    """
    from strata_lookml.diff import diff_findings

    root = Path(repo).expanduser().resolve() if repo else Path.cwd()
    outcome = diff_findings(root, base_ref, head_ref, usage_fixture, schema_fixture)
    new, fixed, unchanged = outcome.new, outcome.fixed, outcome.unchanged_count
    result = outcome.to_dict()
    head_info = outcome.head
    base_commit = outcome.base["commit"]

    if as_json:
        click.echo(json.dumps(result, indent=2, sort_keys=True))
    else:
        click.echo(f"base {base_ref} @ {base_commit[:7]} -> head {head_info['ref']}")
        for marker, records, color in (("+", new, "red"), ("-", fixed, "green")):
            for r in records:
                click.secho(f"{marker} [{r['category']}] {r['label']} ({r['id']})", fg=color)
        click.echo(f"{len(new)} new, {len(fixed)} fixed, {unchanged} unchanged")
    if fail_on_new and new:
        raise SystemExit(1)
