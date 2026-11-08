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


def test_transform_output_is_a_known_column(tmp_path):
    spec = {
        "mark": "bar",
        "transform": [{"calculate": "datum.revenue * 2", "as": "doubled"}],
        "encoding": {"x": {"field": "month"}, "y": {"field": "doubled"}},
    }
    assert _render(spec, tmp_path).exists()


def test_layer_local_transform_output_is_known(tmp_path):
    spec = {
        "layer": [
            {
                "mark": "bar",
                "transform": [{"aggregate": [{"op": "sum", "field": "revenue", "as": "total"}]}],
                "encoding": {"y": {"field": "total"}},
            },
            {"mark": "line", "encoding": {"y": {"field": "revenue"}}},
        ]
    }
    assert _render(spec, tmp_path).exists()


def test_layer_transform_does_not_leak_into_sibling_layer(tmp_path):
    spec = {
        "layer": [
            {"mark": "bar", "transform": [{"calculate": "1", "as": "one"}]},
            {"mark": "line", "encoding": {"y": {"field": "one"}}},
        ]
    }
    assert "one" in _raises(spec, tmp_path)


def test_fold_defaults_to_key_and_value(tmp_path):
    spec = {
        "mark": "bar",
        "transform": [{"fold": ["revenue"]}],
        "encoding": {"x": {"field": "key"}, "y": {"field": "value"}},
    }
    assert _render(spec, tmp_path).exists()


def test_pivot_spec_is_not_rejected(tmp_path):
    spec = {
        "mark": "bar",
        "transform": [{"pivot": "region", "value": "revenue"}],
        "encoding": {"y": {"field": "east"}},
    }
    assert _render(spec, tmp_path).exists()


def test_mismatch_with_unrelated_transform_still_fails(tmp_path):
    spec = {
        "mark": "bar",
        "transform": [{"calculate": "1", "as": "one"}],
        "encoding": {"y": {"field": "nope"}},
    }
    assert "nope" in _raises(spec, tmp_path)


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
