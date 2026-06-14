"""strata query — field-level LookML inspection from the terminal."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from strata.config import load_repo_path


@click.group()
def query() -> None:
    """Inspect the LookML IR from the terminal (no AI client needed).

    These are the same tools the MCP server exposes to AI clients —
    available here for scripting, debugging, or quick lookups.

    Repo is resolved from STRATA_REPO_PATH, ~/.strata/config.json, or cwd.
    Pass --usage-fixture to get query counts and PDT cost data.
    """


def _build(
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
):
    from strata.pipeline import build_graph

    _repo = Path(repo).expanduser().resolve() if repo else _repo_path()
    return build_graph(str(_repo), usage_fixture, schema_fixture)


def _repo_path() -> Path:
    return load_repo_path()


_repo_opt = click.option(
    "--repo",
    default=None,
    envvar="STRATA_REPO_PATH",
    show_envvar=True,
    help="LookML repo path (overrides config)",
)
_usage_opt = click.option(
    "--usage-fixture",
    default=None,
    envvar="STRATA_USAGE_FIXTURE",
    show_envvar=True,
    help="Usage facts JSON for query counts + PDT costs",
)
_schema_opt = click.option(
    "--schema-fixture",
    default=None,
    envvar="STRATA_SCHEMA_FIXTURE",
    show_envvar=True,
    help="Schema facts JSON for drift detection",
)


@query.command("field")
@click.argument("view")
@click.argument("field")
@_repo_opt
@_usage_opt
@_schema_opt
def query_field(
    view: str, field: str, repo: str | None, usage_fixture: str | None, schema_fixture: str | None
) -> None:
    """Show a field's full definition: type, SQL, tags, and usage.

    \b
    Example:
      strata query field orders total_revenue
    """
    graph = _build(repo, usage_fixture, schema_fixture)
    from strata.mcp.tools import strata_query_field

    result = strata_query_field(graph, view, field)
    click.echo(json.dumps(result, indent=2, default=str))


@query.command("explore")
@click.argument("explore")
@click.argument("model")
@_repo_opt
@_usage_opt
@_schema_opt
def query_explore(
    explore: str,
    model: str,
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
) -> None:
    """Show an explore's join graph, base view, and field count.

    \b
    Example:
      strata query explore orders enterprise
    """
    graph = _build(repo, usage_fixture, schema_fixture)
    from strata.mcp.tools import strata_explore_deps

    result = strata_explore_deps(graph, explore, model)
    click.echo(json.dumps(result, indent=2, default=str))


@query.command("orphans")
@click.option(
    "--kind",
    default="all",
    type=click.Choice(["all", "explore", "view", "field"]),
    show_default=True,
    help="Filter by node kind",
)
@_repo_opt
@_usage_opt
@_schema_opt
def query_orphans(
    kind: str, repo: str | None, usage_fixture: str | None, schema_fixture: str | None
) -> None:
    """List orphaned explores, views, or fields with no live dependencies."""
    graph = _build(repo, usage_fixture, schema_fixture)
    from strata.mcp.tools import strata_list_orphans

    result = strata_list_orphans(graph, kind)
    click.echo(json.dumps(result, indent=2, default=str))


@query.command("impact")
@click.argument("physical_table")
@_repo_opt
@_usage_opt
@_schema_opt
def query_impact(
    physical_table: str, repo: str | None, usage_fixture: str | None, schema_fixture: str | None
) -> None:
    """Show every view, explore, and field affected by a physical table change.

    Use before dropping a BQ column or renaming a table.

    \b
    Example:
      strata query impact acme-data.analytics.orders
    """
    graph = _build(repo, usage_fixture, schema_fixture)
    from strata.mcp.tools import strata_impact

    result = strata_impact(graph, physical_table)
    click.echo(json.dumps(result, indent=2, default=str))


@query.command("scope")
@click.argument("files", nargs=-1, required=True)
@_repo_opt
@_usage_opt
@_schema_opt
def query_scope(
    files: tuple[str, ...], repo: str | None, usage_fixture: str | None, schema_fixture: str | None
) -> None:
    """Show which explores are impacted by a set of changed .lkml files.

    Use before merging a PR to know what needs revalidation.

    \b
    Example:
      strata query scope views/orders.view.lkml views/users.view.lkml
    """
    graph = _build(repo, usage_fixture, schema_fixture)
    from strata.mcp.tools import strata_validation_scope

    def _file_to_changed(f: str) -> str:
        stem = Path(f).name
        if ".view." in stem:
            return f"view:{stem.split('.view.')[0]}"
        if ".model." in stem:
            return f"model:{stem.split('.model.')[0]}"
        if ".explore." in stem:
            return f"explore:{stem.split('.explore.')[0]}"
        return f"view:{Path(f).stem}"

    result = strata_validation_scope(graph, [_file_to_changed(f) for f in files])
    click.echo(json.dumps(result, indent=2, default=str))


@query.command("find-field")
@click.argument("query")
@click.option(
    "--kind",
    default="all",
    type=click.Choice(["all", "dimension", "measure", "filter", "parameter"]),
    show_default=True,
    help="Restrict results to a specific field kind",
)
@_repo_opt
@_usage_opt
@_schema_opt
def query_find_field(
    query: str,
    kind: str,
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
) -> None:
    """Search all views for fields matching a name, SQL fragment, or tag.

    Use before adding a field to check if it already exists somewhere in the repo.

    \b
    Example:
      strata query find-field "lifetime_value"
      strata query find-field "orders" --kind measure
    """
    graph = _build(repo, usage_fixture, schema_fixture)
    from strata.mcp.tools import strata_find_field

    result = strata_find_field(graph, query, kind)
    click.echo(json.dumps(result, indent=2, default=str))


@query.command("view-sources")
@click.option("--model", default=None, help="Restrict to views reachable from a specific model")
@_repo_opt
@_usage_opt
@_schema_opt
def query_view_sources(
    model: str | None,
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
) -> None:
    """List all views with their physical BQ table and field counts.

    Use to find which view wraps a given BQ table, or to get a full view inventory.

    \b
    Example:
      strata query view-sources
      strata query view-sources --model ecommerce
    """
    graph = _build(repo, usage_fixture, schema_fixture)
    from strata.mcp.tools import strata_view_sources

    result = strata_view_sources(graph, model)
    click.echo(json.dumps(result, indent=2, default=str))


@query.command("navigate")
@click.argument("anchor")
@click.option("--model", default=None, help="Narrow scope to a specific model")
@click.option("--ticket", default=None, help="Ticket description — infers change type")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit structured JSON")
@click.option(
    "--chart",
    "render_chart",
    is_flag=True,
    default=False,
    help="Render bar chart of view field counts",
)
@click.option(
    "--open",
    "open_chart",
    is_flag=True,
    default=False,
    help="Open chart in browser (implies --chart)",
)
@click.option(
    "--out",
    "out_path",
    default=None,
    type=click.Path(dir_okay=False),
    help="Write the brief as a markdown file to PATH",
)
@_repo_opt
@_usage_opt
@_schema_opt
def query_navigate(
    anchor: str,
    model: str | None,
    ticket: str | None,
    as_json: bool,
    render_chart: bool,
    open_chart: bool,
    out_path: str | None,
    repo: str | None,
    usage_fixture: str | None,
    schema_fixture: str | None,
) -> None:
    """Build a navigator brief for a ticket anchor — no agent needed.

    Classifies the anchor (BQ table, field, view, explore, or .lkml file),
    runs the right lookups, and prints a readable brief showing what exists
    and what to touch. Targets are cited as `file:line` where resolvable.

    \b
    Examples:
      strata query navigate "revenue"
      strata query navigate "project.dataset.orders"
      strata query navigate "orders" --model ecommerce
      strata query navigate "user_id" --ticket "add user region dimension"
      strata query navigate "orders" --chart --open
      strata query navigate "orders" --out brief.md
    """
    from strata.navigate import build_navigate_brief

    graph = _build(repo, usage_fixture, schema_fixture)
    brief = build_navigate_brief(graph, anchor, model, ticket)

    if as_json:
        click.echo(json.dumps(brief, indent=2, default=str))
        if out_path:
            Path(out_path).write_text(_navigate_markdown(anchor, brief), encoding="utf-8")
            click.secho(f"Wrote {out_path}", fg="green", err=True)
        return

    if "error" in brief:
        click.secho(f"Not found: {brief['error']}", fg="red")
        return

    for line in _navigate_lines(anchor, brief):
        click.echo(line)

    if out_path:
        Path(out_path).write_text(_navigate_markdown(anchor, brief), encoding="utf-8")
        click.secho(f"Wrote {out_path}", fg="green")

    # --- Optional chart ---
    if render_chart or open_chart:
        _render_navigate_chart(anchor, brief, open_chart)


def _cite(target: dict[str, Any]) -> str:
    """`file:line` if both known, else `file`, else ''."""
    sf = target.get("source_file")
    if not sf:
        return ""
    sl = target.get("source_line")
    return f"{sf}:{sl}" if sl else sf


def _navigate_lines(anchor: str, brief: dict[str, Any]) -> list[str]:
    """Human-readable brief as a list of lines (shared by stdout + markdown)."""
    out: list[str] = [
        "",
        f"Navigator Brief — {anchor!r}",
        f"Anchor type: {brief['anchor_type']}",
        "",
    ]

    if brief.get("field_matches"):
        out.append(f"Field matches ({len(brief['field_matches'])}):")
        for m in brief["field_matches"][:15]:
            label = f"  [{m['label']}]" if m.get("label") else ""
            out.append(f"  {m['view']}.{m['field']:<30}  {m['type']:<12}  {_cite(m)}{label}")

    if brief.get("bq_fields"):
        fields = brief["bq_fields"]
        out.append(f"Fields ({min(len(fields), 10)} of {len(fields)}):")
        out.extend(f"  {f}" for f in fields[:10])

    if brief.get("views"):
        out.append("")
        out.append(f"Views ({len(brief['views'])}):")
        for v in brief["views"]:
            pt = v.get("physical_table") or "—"
            out.append(f"  {v['name']:<30}  →  {pt}  ({v.get('field_count', '?')} fields)")
            if _cite(v):
                out.append(f"    {_cite(v)}")

    if brief.get("explores"):
        out.append("")
        out.append(f"Explores ({len(brief['explores'])}):")
        for ex in brief["explores"][:5]:
            joins = ", ".join(ex.get("joins", []))
            out.append(f"  {ex['name']:<40}  base={ex['base_view']}  fields={ex['field_count']}")
            if _cite(ex):
                out.append(f"    {_cite(ex)}")
            if joins:
                out.append(f"    joins: {joins}")

    if brief.get("backing_tables"):
        out.append("")
        out.append(f"Backing tables ({len(brief['backing_tables'])}):")
        for v in brief["backing_tables"][:10]:
            out.append(f"  {v['name']:<30}  →  {v.get('physical_table') or '—'}")

    if brief.get("truncated"):
        out.append("")
        out.append(brief["truncated"])

    if brief.get("change_type"):
        out.append("")
        out.append(f"Change type: {brief['change_type']}")
        for action in brief.get("what_to_touch", []):
            out.append(f"  → {action}")

    out.append("")
    return out


def _navigate_markdown(anchor: str, brief: dict[str, Any]) -> str:
    """Render the brief as a portable markdown artifact."""
    if "error" in brief:
        return f"# Navigator Brief — `{anchor}`\n\n> Not found: {brief['error']}\n"

    md = [f"# Navigator Brief — `{anchor}`", "", f"**Anchor type:** {brief['anchor_type']}"]
    if brief.get("change_type"):
        md.append(f"**Change type:** {brief['change_type']}")
    md.append("")

    if brief.get("views"):
        md += ["## Views", "", "| View | Physical table | Fields | Source |", "|---|---|---|---|"]
        for v in brief["views"]:
            md.append(
                f"| `{v['name']}` | {v.get('physical_table') or '—'} "
                f"| {v.get('field_count', '?')} | {_cite(v) or '—'} |"
            )
        md.append("")

    if brief.get("field_matches"):
        md += ["## Field matches", ""]
        for m in brief["field_matches"][:15]:
            md.append(f"- `{m['view']}.{m['field']}` — {m['type']} · {_cite(m) or '—'}")
        md.append("")

    if brief.get("explores"):
        md += ["## Explores", ""]
        for ex in brief["explores"][:5]:
            joins = ", ".join(ex.get("joins", [])) or "—"
            md.append(
                f"- `{ex['name']}` — base `{ex['base_view']}`, {ex['field_count']} fields, "
                f"joins: {joins} · {_cite(ex) or '—'}"
            )
        md.append("")

    if brief.get("bq_fields"):
        md += ["## Fields on table", ""]
        md += [f"- `{f}`" for f in brief["bq_fields"][:20]]
        md.append("")

    if brief.get("what_to_touch"):
        md += ["## What to touch", ""]
        md += [f"{i}. {a}" for i, a in enumerate(brief["what_to_touch"], 1)]
        md.append("")

    if brief.get("truncated"):
        md += [f"> {brief['truncated']}", ""]

    return "\n".join(md)


def _render_navigate_chart(anchor: str, brief: dict[str, Any], open_browser: bool) -> None:
    import tempfile
    import webbrowser

    from strata.mcp.tools import strata_render_chart

    views = brief.get("views") or brief.get("backing_tables") or []
    if not views:
        click.secho("No views to chart.", fg="yellow", err=True)
        return

    rows = [
        {"view": v["name"], "fields": v.get("field_count", 0)}
        for v in views
        if v.get("field_count") is not None
    ]
    if not rows:
        click.secho("No field count data available for chart.", fg="yellow", err=True)
        return

    spec = f"""title: "Navigator — {anchor}"
mark: bar
encoding:
  x:
    field: view
    type: nominal
    sort: "-y"
    title: View
  y:
    field: fields
    type: quantitative
    title: Field Count
show_labels: true
width: 640
height: 400"""

    out_path = str(Path(tempfile.gettempdir()) / f"strata_navigate_{anchor.replace('.', '_')}.html")
    result = strata_render_chart(spec, json.dumps(rows), out_path)
    click.secho(f"Chart: {result['path']}", fg="green")
    if open_browser:
        webbrowser.open(f"file://{result['path']}")


@query.command("status")
@_repo_opt
@_usage_opt
@_schema_opt
def query_status(repo: str | None, usage_fixture: str | None, schema_fixture: str | None) -> None:
    """Show IR summary: node counts, edge count, and cache age.

    Quick sanity check that the repo parsed cleanly and the graph has the
    expected number of explores, views, and fields.

    \b
    $ strata query status --repo tests/lookml/enterprise_mono \\
        --usage-fixture tests/fixtures/enterprise_usage_facts.json
    {
      "node_counts": {"explore": 34, "view": 20, "field": 196, "pdt": 5},
      "edge_count": 378
    }
    """
    graph = _build(repo, usage_fixture, schema_fixture)
    from strata.mcp.tools import strata_ir_status

    result = strata_ir_status(graph)
    click.echo(json.dumps(result, indent=2, default=str))
