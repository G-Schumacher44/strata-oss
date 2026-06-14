"""strata build — parse a LookML repo and write the IR cache."""

from __future__ import annotations

import json

import click


@click.command("build")
@click.option(
    "--repo", required=True, envvar="STRATA_REPO_PATH", show_envvar=True, help="Path to LookML repo"
)
@click.option("--cache", default=None, help="SQLite cache path (default: <repo>/strata_ir.db)")
@click.option(
    "--usage-fixture",
    default=None,
    envvar="STRATA_USAGE_FIXTURE",
    show_envvar=True,
    help="Usage facts JSON for L1 enrichment",
)
@click.option(
    "--schema-fixture",
    default=None,
    envvar="STRATA_SCHEMA_FIXTURE",
    show_envvar=True,
    help="Schema facts JSON for drift detection",
)
@click.option("--json", "as_json", is_flag=True, help="Print status as JSON")
def build_ir(
    repo: str,
    cache: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
    as_json: bool,
) -> None:
    """Parse a LookML repo and write the IR cache (strata_ir.db).

    Pre-builds the SQLite IR so the MCP server loads instantly rather than
    parsing on first tool call. Run this after cloning a new repo or after
    significant LookML changes.

    \b
    strata build --repo tests/lookml/enterprise_mono \\
                 --usage-fixture tests/fixtures/enterprise_usage_facts.json
    """
    from pathlib import Path

    from strata.ir.store import save_ir
    from strata.pipeline import build_graph

    repo_path = Path(repo).expanduser().resolve()
    if not repo_path.exists():
        raise click.ClickException(f"repo does not exist: {repo_path}")

    cache_path = Path(cache).expanduser().resolve() if cache else repo_path / "strata_ir.db"

    graph = build_graph(repo_path, usage_fixture, schema_fixture)
    save_ir(graph, cache_path)

    status = {
        "repo_path": graph.repo_path,
        "built_at": graph.built_at,
        "node_counts": graph.node_counts(),
        "edge_count": len(graph.edges),
        "cache_path": str(cache_path),
    }

    if as_json:
        click.echo(json.dumps(status, sort_keys=True))
    else:
        nc = status["node_counts"]
        click.secho(
            f"Built IR: {nc} nodes, {status['edge_count']} edges → {cache_path}",
            fg="green",
        )
