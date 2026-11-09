"""strata diff — the findings a branch introduces or fixes, against the same usage evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from strata_lookml.cli._contract import JsonCommand


def _classify(
    base: list[dict[str, Any]], head: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """(new, fixed, unchanged_count) by finding id; a duplicated id counts once."""

    def by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {r["id"]: r for r in reversed(records)}  # first record of an id wins

    base_ids, head_ids = by_id(base), by_id(head)
    new = [r for i, r in sorted(head_ids.items()) if i not in base_ids]
    fixed = [r for i, r in sorted(base_ids.items()) if i not in head_ids]
    return new, fixed, len(base_ids.keys() & head_ids.keys())


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
    from strata_lookml.gate import finding_records
    from strata_lookml.pipeline import build_graph
    from strata_lookml.provenance import git_source, materialised, resolve_commit

    root = Path(repo).expanduser().resolve() if repo else Path.cwd()
    base_commit = resolve_commit(root, base_ref)
    head_commit = resolve_commit(root, head_ref) if head_ref else None

    def analyse(commit: str | None) -> list[dict[str, Any]]:
        if commit is None:
            return finding_records(build_graph(root, usage_fixture, schema_fixture))
        with materialised(root, commit) as snapshot:
            return finding_records(build_graph(snapshot, usage_fixture, schema_fixture))

    base_records = analyse(base_commit)
    head_records = analyse(head_commit)
    new, fixed, unchanged = _classify(base_records, head_records)

    head_info: dict[str, Any] = {"ref": head_ref or "working tree", "commit": head_commit}
    if head_commit is None:
        source = git_source(root)
        head_info["commit"] = source["commit"] if source else None
        head_info["dirty"] = bool(source and source["dirty"])
    result = {
        "base": {"ref": base_ref, "commit": base_commit},
        "head": head_info,
        "new": new,
        "fixed": fixed,
        "unchanged_count": unchanged,
    }

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
