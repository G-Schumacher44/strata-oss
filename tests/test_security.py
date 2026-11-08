"""Security constraint tests — HTTPS enforcement, offline L0 boundary, MCP error paths."""

import subprocess
import sys
from pathlib import Path

import pytest

# --- B1: HTTPS enforcement ---


def test_normalize_url_rejects_http_non_localhost():
    from strata_lookml.l1.looker import _normalize_url

    with pytest.raises(ValueError, match="https://"):
        _normalize_url("http://looker.example.com")


def test_normalize_url_allows_https():
    from strata_lookml.l1.looker import _normalize_url

    assert _normalize_url("https://looker.example.com") == "https://looker.example.com"


def test_normalize_url_allows_http_localhost():
    from strata_lookml.l1.looker import _normalize_url

    assert _normalize_url("http://localhost:8765") == "http://localhost:8765"


def test_normalize_url_allows_http_127():
    from strata_lookml.l1.looker import _normalize_url

    assert _normalize_url("http://127.0.0.1:8765") == "http://127.0.0.1:8765"


def test_normalize_url_rejects_bare_hostname():
    from strata_lookml.l1.looker import _normalize_url

    with pytest.raises(ValueError):
        _normalize_url("looker.example.com")


def test_normalize_url_strips_trailing_slash():
    from strata_lookml.l1.looker import _normalize_url

    assert _normalize_url("https://looker.example.com/") == "https://looker.example.com"


# --- B8: Offline L0 import guard ---


def test_l0_no_network_imports():
    """L0 IR + pipeline imports must not pull in third-party HTTP/LLM libraries."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import strata_lookml.ir.parser, strata_lookml.ir.types, strata_lookml.pipeline; "
                "import sys; "
                "bad = [m for m in sys.modules "
                "       if any(x in m for x in "
                "           ('requests', 'httpx', 'urllib3', 'anthropic', 'openai', "
                "            'google.generativeai', 'langchain', 'httplib2'))"
                "       ]; "
                "assert not bad, f'third-party network/LLM module imported in L0: {bad}'"
            ),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"L0 constraint violated:\n{result.stdout}\n{result.stderr}"


# --- B2: MCP tool error paths ---


def _make_graph():
    from strata_lookml.pipeline import build_graph

    lookml_dir = Path(__file__).parent / "lookml" / "thelook"
    fixtures_dir = Path(__file__).parent / "fixtures"
    return build_graph(
        str(lookml_dir),
        str(fixtures_dir / "playground_usage_facts.json"),
        str(fixtures_dir / "playground_schema_facts.json"),
    )


def test_mcp_query_field_unknown_returns_error():
    from strata_lookml.mcp.tools import strata_query_field

    graph = _make_graph()
    result = strata_query_field(graph, "nonexistent_view", "nonexistent_field")
    assert "error" in result


def test_mcp_explore_deps_unknown_returns_error():
    from strata_lookml.mcp.tools import strata_explore_deps

    graph = _make_graph()
    result = strata_explore_deps(graph, "nonexistent_explore", "nonexistent_model")
    assert "error" in result


def test_mcp_impact_unknown_table_returns_error():
    from strata_lookml.mcp.tools import strata_impact

    graph = _make_graph()
    result = strata_impact(graph, "nonexistent_table")
    assert "error" in result


def test_mcp_skill_unknown_returns_string_error():
    from strata_lookml.mcp.tools import strata_skill

    skills_dir = Path(__file__).resolve().parent.parent / "src" / "strata_lookml" / "skills"
    result = strata_skill(str(skills_dir), "nonexistent_skill_xyz")
    assert "not found" in result


# --- B6: Chart output path ---


def test_render_chart_rejects_path_escape():
    from strata_lookml.mcp.tools import strata_render_chart

    spec_yaml = "mark: bar\nencoding:\n  x:\n    field: category\n  y:\n    field: value"
    data_json = '[{"category": "A", "value": 1}]'
    with pytest.raises(ValueError, match="out_path must be within"):
        strata_render_chart(spec_yaml, data_json, "/etc/strata_pwned.html")


def test_render_chart_rejects_adjacent_directory_prefix_collision():
    # Regression: "/tmp-evil/x.html".startswith("/tmp") is True — startswith must not be used.
    # Path.is_relative_to() correctly rejects adjacent directories sharing a prefix.
    from strata_lookml.mcp.tools import strata_render_chart

    spec_yaml = "mark: bar\nencoding:\n  x:\n    field: category\n  y:\n    field: value"
    data_json = '[{"category": "A", "value": 1}]'
    with pytest.raises(ValueError, match="out_path must be within"):
        strata_render_chart(spec_yaml, data_json, "/tmp-evil/strata_pwned.html")


def test_render_chart_html_cannot_break_out_of_script_block(tmp_path):
    # Regression: json.dumps leaves "<" raw, so a "</script>" in a data value ended the
    # embed <script> and the remainder parsed as markup.
    from strata_lookml.viz.render import render_chart

    out = render_chart(
        {"mark": "bar"}, [{"k": "</script><img src=x onerror=alert(1)>"}], tmp_path / "c.html"
    )
    html = out.read_text(encoding="utf-8")
    embed = html.split("vegaEmbed(", 1)[1]
    assert "</script><img" not in html
    assert "\\u003c/script>\\u003cimg" in embed


# --- generate-schema: repo-controlled table names never reach the BigQuery CLI unchecked ---

_INJECTION_VIEWS = """
view: evil_table {
  sql_table_name: `proj.ds.x') ; DROP SCHEMA victim_ds CASCADE ; -- ` ;;
  dimension: id { sql: ${TABLE}.id ;; }
}
view: evil_dataset {
  sql_table_name: `proj.ds` ; DROP SCHEMA victim_ds ; --.t` ;;
  dimension: id { sql: ${TABLE}.id ;; }
}
view: good {
  sql_table_name: `proj-1.ds_a.orders` ;;
  dimension: id { sql: ${TABLE}.id ;; }
}
"""


def test_generate_schema_rejects_hostile_identifiers_before_bq(tmp_path, monkeypatch):
    """Names with quotes, backticks, semicolons or whitespace are skipped and reported; only the
    valid table is queried, and its name travels as a query parameter, not SQL text."""
    from click.testing import CliRunner

    import strata_lookml.cli.generate_schema as gs

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "v.view.lkml").write_text(_INJECTION_VIEWS, encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="[]", stderr="")

    monkeypatch.setattr(gs.subprocess, "run", fake_run)
    result = CliRunner().invoke(
        gs.generate_schema, ["--repo", str(repo), "--out", str(tmp_path / "out.json")]
    )

    assert result.exit_code == 0, result.output
    assert "Rejected (invalid BigQuery identifier, not queried): 2" in result.output
    assert len(calls) == 1
    argv = calls[0]
    assert all("DROP" not in arg and "victim_ds" not in arg for arg in argv)
    assert '--parameter=names:ARRAY<STRING>:["orders"]' in argv
    assert argv[-1] == (
        "SELECT table_name, column_name FROM `proj-1.ds_a.INFORMATION_SCHEMA.COLUMNS` "
        "WHERE table_name IN UNNEST(@names) ORDER BY table_name, ordinal_position"
    )
    assert "--max_rows=1000000" in argv


@pytest.mark.parametrize(
    ("dataset", "names"),
    [
        ("proj.ds` ; DROP SCHEMA v ; --", ["t"]),
        ("proj.ds", ["x') ; DROP SCHEMA victim_ds CASCADE ; -- "]),
        ("proj.ds.extra", ["t"]),
        ("proj.ds", ["has space"]),
    ],
)
def test_build_columns_query_refuses_invalid_identifiers(dataset, names):
    """Defense in depth: the argv builder itself refuses, whatever the caller validated."""
    from strata_lookml.cli.generate_schema import build_columns_query

    with pytest.raises(ValueError, match="invalid BigQuery"):
        build_columns_query(dataset, names)


# --- Local-surface hardening ---


def test_cache_age_rejects_future_built_at(tmp_path):
    """A future built_at would make a stale cache look fresh forever; it must read as unknown."""
    import sqlite3
    from datetime import UTC, datetime, timedelta

    from strata_lookml.ir.store import cache_age_seconds, save_ir

    cache = tmp_path / "strata_ir.db"
    save_ir(_make_graph(), cache)
    assert cache_age_seconds(cache) is not None
    future = (datetime.now(UTC) + timedelta(days=365)).isoformat()
    with sqlite3.connect(cache) as conn:
        conn.execute("UPDATE ir_cache SET built_at = ? WHERE id = 1", (future,))
    assert cache_age_seconds(cache) is None


def test_render_chart_keeps_stdout_clean_and_requires_html(tmp_path, capsys):
    """stdout is the MCP JSON-RPC channel; the chart path goes to stderr."""
    from strata_lookml.mcp.tools import strata_render_chart

    spec = "mark: bar"
    out = Path("/tmp") / f"strata_test_{tmp_path.name}.html"
    try:
        strata_render_chart(spec, "[]", str(out))
        captured = capsys.readouterr()
        assert captured.out == ""
        assert str(out) in captured.err
    finally:
        out.unlink(missing_ok=True)
    with pytest.raises(ValueError, match=r"\.html"):
        strata_render_chart(spec, "[]", "/tmp/strata_test_chart.sh")


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_parse_repo_skips_symlinks_that_escape_the_repo(tmp_path):
    from strata_lookml.ir.parser import parse_repo

    outside = tmp_path / "outside.view.lkml"
    outside.write_text("view: secret { dimension: x { sql: 1 ;; } }\n", encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "ok.view.lkml").write_text("view: ok { dimension: y { sql: 1 ;; } }\n")
    (repo / "inside_link.view.lkml").symlink_to(repo / "ok.view.lkml")
    (repo / "escape.view.lkml").symlink_to(outside)
    (repo / "dir_link").symlink_to(tmp_path, target_is_directory=True)

    names = sorted(f.path for f in parse_repo(repo))
    assert all("escape" not in n and "dir_link" not in n for n in names), names
    assert any(n.endswith("ok.view.lkml") for n in names)
    assert any(n.endswith("inside_link.view.lkml") for n in names)


# --- Chart output: no fixed shared path, no symlink following ---

_CHART_SPEC = {"mark": "bar", "encoding": {"x": {"field": "c"}, "y": {"field": "v"}}}
_CHART_ROWS = [{"c": "A", "v": 1}]


def test_render_chart_default_path_is_fresh_and_not_fixed(tmp_path, monkeypatch):
    import tempfile

    from strata_lookml.viz.render import render_chart

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    first = render_chart(dict(_CHART_SPEC), _CHART_ROWS)
    second = render_chart(dict(_CHART_SPEC), _CHART_ROWS)
    assert first != second
    assert first.name != "strata_chart.html" and first.name.startswith("strata_chart_")
    assert first.parent == tmp_path and first.read_text(encoding="utf-8").startswith("<")


def test_render_chart_explicit_path_writes_normally(tmp_path):
    from strata_lookml.viz.render import render_chart

    out = tmp_path / "sub" / "c.html"
    assert render_chart(dict(_CHART_SPEC), _CHART_ROWS, out) == out
    assert "vega" in out.read_text(encoding="utf-8").lower()


def test_render_chart_refuses_symlink_at_target(tmp_path):
    from strata_lookml.viz.render import render_chart

    victim = tmp_path / "victim.txt"
    victim.write_text("keep", encoding="utf-8")
    link = tmp_path / "c.html"
    link.symlink_to(victim)
    with pytest.raises(ValueError, match="symlink"):
        render_chart(dict(_CHART_SPEC), _CHART_ROWS, link)
    assert victim.read_text(encoding="utf-8") == "keep"


def test_mcp_render_chart_refuses_symlink_under_allowed_root(tmp_path, monkeypatch):
    from strata_lookml.mcp.tools import chart_output_dir, strata_render_chart

    monkeypatch.setenv("HOME", str(tmp_path))
    out_dir = chart_output_dir()
    out_dir.mkdir(parents=True)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep", encoding="utf-8")
    (out_dir / "c.html").symlink_to(victim)
    spec_yaml = "mark: bar\nencoding:\n  x:\n    field: c\n  y:\n    field: v"
    with pytest.raises(ValueError, match="symlink"):
        strata_render_chart(spec_yaml, '[{"c": "A", "v": 1}]', str(out_dir / "c.html"))
    assert victim.read_text(encoding="utf-8") == "keep"
