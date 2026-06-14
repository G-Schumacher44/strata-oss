"""strata check — offline CI scenario gates."""

from __future__ import annotations

import sys

import click


@click.command("check")
@click.option(
    "--repo",
    default=None,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="Path to LookML repo (defaults to cwd)",
)
@click.option(
    "--usage-fixture",
    default=None,
    envvar="STRATA_USAGE_FIXTURE",
    show_envvar=True,
    help="Usage facts JSON — explore query counts and PDT build costs.",
)
@click.option(
    "--schema-fixture",
    default=None,
    envvar="STRATA_SCHEMA_FIXTURE",
    show_envvar=True,
    help="Schema facts JSON — warehouse column inventory for drift detection.",
)
def check(repo: str | None, usage_fixture: str | None, schema_fixture: str | None) -> None:
    """Run offline LookML governance gates (dead code, drift, PDT costs, validation).

    Exits 0 if all checks pass, 1 if any fail. Use in CI to gate LookML PRs.
    Point at one of the included playgrounds to try it:

    \b
    strata check \\
      --repo tests/lookml/enterprise_mono \\
      --usage-fixture tests/fixtures/enterprise_usage_facts.json
    """
    from pathlib import Path

    from strata.pipeline import build_graph
    from strata.synthesis.slices import build_explore_slice
    from strata.synthesis.verdicts import deterministic_verdict, validate_verdict

    _repo = Path(repo).expanduser().resolve() if repo else Path.cwd()
    graph = build_graph(str(_repo), usage_fixture, schema_fixture)

    failures: list[str] = []
    if graph.metadata.get("resolution_errors"):
        failures.append(f"resolution errors: {graph.metadata['resolution_errors']}")
    if not graph.metadata.get("l1", {}).get("dead_code"):
        failures.append("expected at least one dead-code record")
    if not graph.metadata.get("l1", {}).get("pdt_ledger"):
        failures.append("expected at least one PDT ledger record")
    if not graph.metadata.get("l1", {}).get("schema_drift"):
        failures.append("expected at least one schema-drift record")

    for node in graph.nodes_by_kind("explore"):
        explore_slice = build_explore_slice(graph, node.attrs["model"], node.name)
        verdict = deterministic_verdict(explore_slice)
        failures.extend(validate_verdict(verdict, explore_slice["evidence_ids"]))

    if failures:
        for f in failures:
            click.secho(f"FAIL: {f}", fg="red", err=True)
        sys.exit(1)

    click.secho("Strata scenario gates passed.", fg="green")
