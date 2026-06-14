"""Security constraint tests — HTTPS enforcement, offline L0 boundary, MCP error paths."""

import subprocess
import sys
from pathlib import Path

import pytest

# --- B1: HTTPS enforcement ---


def test_normalize_url_rejects_http_non_localhost():
    from strata.l1.looker import _normalize_url

    with pytest.raises(ValueError, match="https://"):
        _normalize_url("http://looker.example.com")


def test_normalize_url_allows_https():
    from strata.l1.looker import _normalize_url

    assert _normalize_url("https://looker.example.com") == "https://looker.example.com"


def test_normalize_url_allows_http_localhost():
    from strata.l1.looker import _normalize_url

    assert _normalize_url("http://localhost:8765") == "http://localhost:8765"


def test_normalize_url_allows_http_127():
    from strata.l1.looker import _normalize_url

    assert _normalize_url("http://127.0.0.1:8765") == "http://127.0.0.1:8765"


def test_normalize_url_rejects_bare_hostname():
    from strata.l1.looker import _normalize_url

    with pytest.raises(ValueError):
        _normalize_url("looker.example.com")


def test_normalize_url_strips_trailing_slash():
    from strata.l1.looker import _normalize_url

    assert _normalize_url("https://looker.example.com/") == "https://looker.example.com"


# --- B8: Offline L0 import guard ---


def test_l0_no_network_imports():
    """L0 IR + pipeline imports must not pull in third-party HTTP/LLM libraries."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import strata.ir.parser, strata.ir.types, strata.pipeline; "
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
    from strata.pipeline import build_graph

    lookml_dir = Path(__file__).parent / "lookml" / "thelook"
    fixtures_dir = Path(__file__).parent / "fixtures"
    return build_graph(
        str(lookml_dir),
        str(fixtures_dir / "playground_usage_facts.json"),
        str(fixtures_dir / "playground_schema_facts.json"),
    )


def test_mcp_query_field_unknown_returns_error():
    from strata.mcp.tools import strata_query_field

    graph = _make_graph()
    result = strata_query_field(graph, "nonexistent_view", "nonexistent_field")
    assert "error" in result


def test_mcp_explore_deps_unknown_returns_error():
    from strata.mcp.tools import strata_explore_deps

    graph = _make_graph()
    result = strata_explore_deps(graph, "nonexistent_explore", "nonexistent_model")
    assert "error" in result


def test_mcp_impact_unknown_table_returns_error():
    from strata.mcp.tools import strata_impact

    graph = _make_graph()
    result = strata_impact(graph, "nonexistent_table")
    assert "error" in result


def test_mcp_skill_unknown_returns_string_error():
    from strata.mcp.tools import strata_skill

    skills_dir = Path(__file__).resolve().parent.parent / "src" / "strata" / "skills"
    result = strata_skill(str(skills_dir), "nonexistent_skill_xyz")
    assert "not found" in result


# --- B6: Chart output path ---


def test_render_chart_rejects_path_escape():
    from strata.mcp.tools import strata_render_chart

    spec_yaml = "mark: bar\nencoding:\n  x:\n    field: category\n  y:\n    field: value"
    data_json = '[{"category": "A", "value": 1}]'
    with pytest.raises(ValueError, match="out_path must be within"):
        strata_render_chart(spec_yaml, data_json, "/etc/strata_pwned.html")
