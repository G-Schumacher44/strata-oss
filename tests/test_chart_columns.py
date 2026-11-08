"""Chart encoding columns are validated against the data; templates take --x/--y/--color."""

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_error_contract import _call_tool

REPO_ROOT = Path(__file__).resolve().parents[1]
ROWS = [
    {"month": "2026-01-01", "revenue": 10, "region": "east"},
    {"month": "2026-02-01", "revenue": 12, "region": "west"},
]


def _cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "strata_lookml.cli.main", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=os.environ,
    )


def _data(tmp_path: Path) -> Path:
    data = tmp_path / "data.json"
    data.write_text(json.dumps(ROWS), encoding="utf-8")
    return data


def test_chart_line_with_mismatched_columns_exits_1_listing_both_sets(tmp_path):
    result = _cli("chart", "line", str(_data(tmp_path)), "--out", str(tmp_path / "c.html"))

    assert result.returncode == 1
    assert "date, value" in result.stderr
    assert "month, region, revenue" in result.stderr
    assert not (tmp_path / "c.html").exists()


def test_chart_line_x_y_overrides_render(tmp_path):
    out = tmp_path / "c.html"
    result = _cli(
        "chart", "line", str(_data(tmp_path)), "--x", "month", "--y", "revenue", "--out", str(out)
    )

    assert result.returncode == 0, result.stderr
    assert '"field": "month"' in out.read_text(encoding="utf-8")


def test_chart_color_override_adds_the_channel(tmp_path):
    out = tmp_path / "c.html"
    result = _cli(
        "chart", "line", str(_data(tmp_path)), "--x", "month", "--y", "revenue",
        "--color", "region", "--out", str(out),
    )  # fmt: skip

    assert result.returncode == 0, result.stderr
    assert '"field": "region"' in out.read_text(encoding="utf-8")


def test_template_help_lists_required_columns_from_the_yaml():
    result = _cli("chart", "line", "--help")

    assert "x=date, y=value" in result.stdout
    assert "--x" in result.stdout


def test_mcp_render_chart_column_mismatch_is_an_error_listing_columns():
    spec = "mark: line\nencoding:\n  x: {field: date, type: temporal}\n  y: {field: value}\n"
    result = _call_tool(
        "strata_render_chart",
        {"spec_yaml": spec, "data_json": json.dumps(ROWS), "out_path": "/tmp/strata_s10.html"},
    )

    assert result.is_error is True
    text = result.content[0].text
    assert "date, value" in text
    assert "month, region, revenue" in text


def _render(spec: dict, tmp_path: Path, rows: list[dict] | None = None) -> Path:
    from strata_lookml.viz.render import render_chart

    return render_chart(spec, ROWS if rows is None else rows, tmp_path / "c.html")


def _raises(spec: dict, tmp_path: Path, rows: list[dict] | None = None) -> str:
    import pytest

    from strata_lookml.errors import InvalidInput

    with pytest.raises(InvalidInput) as err:
        _render(spec, tmp_path, rows)
    return str(err.value)


def test_field_access_paths(tmp_path):
    from strata_lookml.viz.render import _first_path_component as first

    assert first("a.b") == "a"
    assert first("values[0]") == "values"
    assert first('a["b.c"]') == "a"
    assert first("orders\\.revenue") == "orders.revenue"
    assert first('["a.b"]') == "a.b"

    rows = [{"orders.revenue": 1, "values": [1], "nested": {"k": 1}}]
    for field in ("orders\\.revenue", "values[0]", "nested.k", 'nested["k"]'):
        assert _render({"mark": "bar", "encoding": {"y": {"field": field}}}, tmp_path, rows)
    assert "orders.revenue" in _raises(
        {"mark": "bar", "encoding": {"y": {"field": "orders.revenue"}}}, tmp_path, rows
    )


def test_layer_with_inline_data_is_checked_against_its_own_rows(tmp_path):
    rule = {"mark": "rule", "data": {"values": [{"threshold": 20}]}}
    layers = [{"mark": "line", "encoding": {"y": {"field": "revenue"}}}]
    ok = {"layer": [*layers, {**rule, "encoding": {"y": {"field": "threshold"}}}]}
    assert _render(ok, tmp_path).exists()
    bad = {"layer": [*layers, {**rule, "encoding": {"y": {"field": "revenue"}}}]}
    assert "revenue" in _raises(bad, tmp_path)


def test_layer_with_uninspectable_data_is_skipped(tmp_path):
    spec = {
        "layer": [
            {"mark": "rule", "data": {"url": "t.csv"}, "encoding": {"y": {"field": "anything"}}},
        ]
    }
    assert _render(spec, tmp_path).exists()


def test_inheriting_layer_mismatch_still_fails(tmp_path):
    spec = {"layer": [{"mark": "line", "encoding": {"y": {"field": "nope"}}}]}
    assert "nope" in _raises(spec, tmp_path)


def test_array_encoding_fields_are_checked_and_accepted(tmp_path):
    tip = {"mark": "bar", "encoding": {"tooltip": [{"field": "month"}, {"field": "revenue"}]}}
    assert _render(tip, tmp_path).exists()
    bad = {"mark": "bar", "encoding": {"tooltip": [{"field": "month"}, {"field": "nope"}]}}
    assert "nope" in _raises(bad, tmp_path)


def _cli_charts(charts: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "strata_lookml.cli.main", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "STRATA_CHARTS_PATH": str(charts)},
    )


def test_array_tooltip_template_keeps_cli_and_help_working(tmp_path):
    charts = tmp_path / "charts"
    charts.mkdir()
    (charts / "bar.yml").write_text(
        "mark: bar\nencoding:\n  x: {field: category}\n  y: {field: value}\n"
        "  tooltip: [{field: category}, {field: value}]\n",
        encoding="utf-8",
    )
    assert _cli_charts(charts, "--help").returncode == 0
    result = _cli_charts(charts, "chart", "bar", "--help")
    assert result.returncode == 0, result.stderr
    assert "x=category" in result.stdout
    assert "tooltip=category,value" in result.stdout


def test_malformed_template_does_not_break_startup(tmp_path):
    charts = tmp_path / "charts"
    charts.mkdir()
    (charts / "bar.yml").write_text("mark: [unclosed\n  : :\n", encoding="utf-8")
    assert _cli_charts(charts, "--help").returncode == 0
    assert _cli_charts(charts, "chart", "bar", "--help").returncode == 0


def test_transform_specs_are_not_validated(tmp_path):
    # Vega-Lite decides a transform's outputs (here bin's implicit `_end`), so we do not guess.
    spec = {
        "mark": "bar",
        "transform": [{"bin": True, "field": "revenue", "as": "rev"}],
        "encoding": {"x": {"field": "rev"}, "x2": {"field": "rev_end"}},
    }
    assert _render(spec, tmp_path).exists()
    layered = {
        "layer": [
            {
                "mark": "bar",
                "transform": [{"calculate": "1", "as": "one"}],
                "encoding": {"y": {"field": "one"}},
            }
        ]
    }
    assert _render(layered, tmp_path).exists()


def test_layer_without_transform_still_fails_beside_a_transform_layer(tmp_path):
    spec = {
        "layer": [
            {"mark": "bar", "transform": [{"calculate": "1", "as": "one"}]},
            {"mark": "line", "encoding": {"y": {"field": "nope"}}},
        ]
    }
    assert "nope" in _raises(spec, tmp_path)


def test_count_channel_is_not_validated(tmp_path):
    spec = {
        "mark": "bar",
        "encoding": {
            "x": {"field": "month"},
            "y": {"aggregate": "count", "field": "anything"},
            "color": {"field": "*"},
        },
    }
    assert _render(spec, tmp_path).exists()
