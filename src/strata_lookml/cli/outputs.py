"""strata outputs — generate offline review artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from strata_lookml.ir.types import IRGraph


def live_looker_graph(repo: str, looker_url: str, days: int, schema_fixture: str | None) -> IRGraph:
    """Live-enriched graph; token/API refusals surface as CLI errors, not tracebacks."""
    from strata_lookml.l1.looker import LiveLookerNotConfigured, LookerAPIError
    from strata_lookml.pipeline import build_graph_from_looker

    try:
        return build_graph_from_looker(repo, looker_url, days, schema_fixture)
    except (LiveLookerNotConfigured, LookerAPIError) as exc:
        raise click.ClickException(str(exc)) from exc


@click.command("outputs")
@click.option(
    "--repo", required=True, envvar="STRATA_REPO_PATH", show_envvar=True, help="Path to LookML repo"
)
@click.option("--out", required=True, help="Output directory for JSON artifacts")
@click.option(
    "--usage-fixture",
    default=None,
    envvar="STRATA_USAGE_FIXTURE",
    show_envvar=True,
    help="Usage facts JSON (explore query counts + PDT build costs). "
    "Omit to run L0-only (no dead code detection without usage data).",
)
@click.option(
    "--schema-fixture",
    default=None,
    envvar="STRATA_SCHEMA_FIXTURE",
    show_envvar=True,
    help="Schema facts JSON (warehouse column inventory for drift detection).",
)
@click.option(
    "--looker-url",
    default=None,
    help="Looker API host URL for live L1 enrichment — the URL the `strata auth login` token was issued for (usually the instance URL)",
)
@click.option(
    "--days",
    default=30,
    show_default=True,
    help="Usage window in days when fetching live from Looker",
)
@click.option(
    "--validation-scope-fixture",
    default=None,
    help="JSON file listing explores/views to scope validation reporting",
)
def outputs(
    repo: str,
    out: str,
    usage_fixture: str | None,
    schema_fixture: str | None,
    looker_url: str | None,
    days: int,
    validation_scope_fixture: str | None,
) -> None:
    """Build the IR and write JSON artifacts (dead code, PDT costs, drift, catalog).

    Writes one JSON file per artifact type to OUT/. Use these as input to
    `strata dashboard` or feed them directly to your reporting pipeline.
    """
    from strata_lookml.outputs import write_artifacts
    from strata_lookml.pipeline import build_graph

    if looker_url:
        graph = live_looker_graph(repo, looker_url, days, schema_fixture)
    else:
        graph = build_graph(repo, usage_fixture, schema_fixture)

    if validation_scope_fixture:
        scope_data = json.loads(Path(validation_scope_fixture).read_text(encoding="utf-8"))
        graph.metadata["validation_scope_inputs"] = scope_data.get("changed", scope_data)

    written = write_artifacts(graph, out)
    click.echo(json.dumps(written, indent=2, sort_keys=True))
