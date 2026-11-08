"""strata chart — ad-hoc Vega-Lite chart rendering."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from strata_lookml.viz.render import _CHARTS_DIR, _load_data, _load_spec, render_chart

_OUT_HELP = (
    "Output HTML path (default: a fresh strata_chart_*.html in the system temp dir; "
    "the path written is printed). Refuses to write through a symlink."
)


def _template_help(name: str, summary: str) -> str:
    """Command help: the summary plus the template's columns, read from its YAML.

    Help is decoration: a template that cannot be read for it falls back to the plain summary
    rather than breaking CLI startup.
    """
    try:
        encoding = _load_spec(_CHARTS_DIR / f"{name}.yml").get("encoding", {})
        required: list[str] = []
        optional: list[str] = []
        for channel, enc in encoding.items():
            # A channel is one definition or a list of them (e.g. `tooltip`).
            fields = [
                item["field"]
                for item in (enc if isinstance(enc, list) else [enc])
                if isinstance(item, dict) and item.get("field")
            ]
            if fields:
                required.append(f"{channel}={','.join(fields)}")
            else:
                optional.append(channel)
    except Exception:
        return summary
    text = f"{summary}\n\nRequired columns (default names): {', '.join(required)}."
    if optional:
        text += f" Optional channels: {', '.join(optional)}."
    return text + " Use --x/--y/--color to map your own columns."


def _template_options(func: Callable[..., None]) -> Callable[..., None]:
    for decorator in reversed(
        [
            click.argument("data", type=click.Path(exists=True)),
            click.option("--x", "x_col", help="Data column for the x channel"),
            click.option("--y", "y_col", help="Data column for the y channel"),
            click.option("--color", "color_col", help="Data column for the color channel"),
            click.option("--title", help="Chart title"),
            click.option("--out", default=None, help=_OUT_HELP),
            click.option("--open", "open_browser", is_flag=True, help="Open in browser"),
        ]
    ):
        func = decorator(func)
    return func


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


def _template_command(name: str, summary: str) -> None:
    @chart.command(name, help=_template_help(name, summary))
    @_template_options
    def command(
        data: str,
        x_col: str | None,
        y_col: str | None,
        color_col: str | None,
        title: str | None,
        out: str | None,
        open_browser: bool,
    ) -> None:
        _render(name, data, {"x": x_col, "y": y_col, "color": color_col}, title, out, open_browser)


_template_command("bar", "Categorical comparison — one dimension vs one measure.")
_template_command("line", "Trend over time.")
_template_command("scatter", "Correlation between two measures.")
_template_command("heatmap", "Two-dimensional breakdown with color intensity.")


@chart.command("render")
@click.argument("data", type=click.Path(exists=True))
@click.option(
    "--spec", required=True, type=click.Path(exists=True), help="Custom YAML/JSON spec file"
)
@click.option("--title", help="Override chart title")
@click.option("--out", default=None, help=_OUT_HELP)
@click.option("--open", "open_browser", is_flag=True, help="Open in browser")
def chart_render(
    data: str, spec: str, title: str | None, out: str | None, open_browser: bool
) -> None:
    """Render a custom spec file against a data file."""
    vl_spec = _load_spec(Path(spec))
    rows = _load_data(Path(data))
    if title:
        vl_spec["title"] = title
    render_chart(vl_spec, rows, Path(out) if out else None, open_browser=open_browser)


def _render(
    chart_type: str,
    data: str,
    overrides: dict[str, str | None],
    title: str | None,
    out: str | None,
    open_browser: bool,
) -> None:
    spec_path = _CHARTS_DIR / f"{chart_type}.yml"
    if not spec_path.exists():
        raise click.ClickException(f"Chart template not found: {spec_path}")
    vl_spec = _load_spec(spec_path)
    rows = _load_data(Path(data))
    if title:
        vl_spec["title"] = title
    _apply_overrides(vl_spec, overrides)
    render_chart(vl_spec, rows, Path(out) if out else None, open_browser=open_browser)


def _apply_overrides(spec: dict[str, Any], overrides: dict[str, str | None]) -> None:
    """Point template channels at the user's columns (no renaming of the data)."""
    encoding = spec.setdefault("encoding", {})
    for channel, column in overrides.items():
        if column:
            encoding.setdefault(channel, {"type": "nominal"})["field"] = column
