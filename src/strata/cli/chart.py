"""strata chart — ad-hoc Vega-Lite chart rendering."""

from __future__ import annotations

from pathlib import Path

import click

from strata.viz.render import _CHARTS_DIR, _load_data, _load_spec, render_chart


@click.group()
def chart() -> None:
    """Render ad-hoc charts from data files."""


@chart.command("list")
def chart_list() -> None:
    """List available chart types."""
    if not _CHARTS_DIR.exists():
        click.echo("No chart templates found.")
        return
    for t in sorted(_CHARTS_DIR.glob("*.yml")):
        click.echo(t.stem)


@chart.command("bar")
@click.argument("data", type=click.Path(exists=True))
@click.option("--title", help="Chart title")
@click.option("--out", default="/tmp/strata_chart.html", show_default=True)
@click.option("--open", "open_browser", is_flag=True, help="Open in browser")
def chart_bar(data: str, title: str | None, out: str, open_browser: bool) -> None:
    """Categorical comparison — one dimension vs one measure."""
    _render("bar", data, title, out, open_browser)


@chart.command("line")
@click.argument("data", type=click.Path(exists=True))
@click.option("--title", help="Chart title")
@click.option("--out", default="/tmp/strata_chart.html", show_default=True)
@click.option("--open", "open_browser", is_flag=True, help="Open in browser")
def chart_line(data: str, title: str | None, out: str, open_browser: bool) -> None:
    """Trend over time."""
    _render("line", data, title, out, open_browser)


@chart.command("scatter")
@click.argument("data", type=click.Path(exists=True))
@click.option("--title", help="Chart title")
@click.option("--out", default="/tmp/strata_chart.html", show_default=True)
@click.option("--open", "open_browser", is_flag=True, help="Open in browser")
def chart_scatter(data: str, title: str | None, out: str, open_browser: bool) -> None:
    """Correlation between two measures."""
    _render("scatter", data, title, out, open_browser)


@chart.command("heatmap")
@click.argument("data", type=click.Path(exists=True))
@click.option("--title", help="Chart title")
@click.option("--out", default="/tmp/strata_chart.html", show_default=True)
@click.option("--open", "open_browser", is_flag=True, help="Open in browser")
def chart_heatmap(data: str, title: str | None, out: str, open_browser: bool) -> None:
    """Two-dimensional breakdown with color intensity."""
    _render("heatmap", data, title, out, open_browser)


@chart.command("render")
@click.argument("data", type=click.Path(exists=True))
@click.option(
    "--spec", required=True, type=click.Path(exists=True), help="Custom YAML/JSON spec file"
)
@click.option("--title", help="Override chart title")
@click.option("--out", default="/tmp/strata_chart.html", show_default=True)
@click.option("--open", "open_browser", is_flag=True, help="Open in browser")
def chart_render(data: str, spec: str, title: str | None, out: str, open_browser: bool) -> None:
    """Render a custom spec file against a data file."""
    vl_spec = _load_spec(Path(spec))
    rows = _load_data(Path(data))
    if title:
        vl_spec["title"] = title
    render_chart(vl_spec, rows, Path(out), open_browser=open_browser)


def _render(chart_type: str, data: str, title: str | None, out: str, open_browser: bool) -> None:
    spec_path = _CHARTS_DIR / f"{chart_type}.yml"
    if not spec_path.exists():
        raise click.ClickException(f"Chart template not found: {spec_path}")
    vl_spec = _load_spec(spec_path)
    rows = _load_data(Path(data))
    if title:
        vl_spec["title"] = title
    render_chart(vl_spec, rows, Path(out), open_browser=open_browser)
