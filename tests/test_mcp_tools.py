from pathlib import Path

from strata.ir.resolver import build_resolved_graph
from strata.mcp.tools import (
    strata_chart_templates,
    strata_conductor_status,
    strata_dead_code_register,
    strata_explore_deps,
    strata_find_field,
    strata_impact,
    strata_ir_status,
    strata_list_orphans,
    strata_list_skills,
    strata_pdt_costs,
    strata_query_field,
    strata_schema_drift,
    strata_skill,
    strata_usage_summary,
    strata_validation_scope,
    strata_view_sources,
)
from strata.navigate import build_navigate_brief

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "src" / "strata" / "skills"

FIXTURES = Path(__file__).parent / "fixtures"
# Use a committed fixture, not the live repo conductor/, so the test is
# deterministic and survives public sanitization (handoff-log.md is stripped
# from the public mirror by .publicignore).
CONDUCTOR_DIR = FIXTURES / "conductor"


def test_strata_query_field():
    graph = build_resolved_graph(FIXTURES)

    field = strata_query_field(graph, "customer_extended", "email")

    assert field == {
        "sql": "LOWER(${TABLE}.email)",
        "type": "string",
        "tags": ["normalized"],
        "source_file": "customer_extended.view.lkml",
        "resolution_chain": ["base_customer", "customer_extended"],
    }


def test_strata_list_orphans():
    graph = build_resolved_graph(FIXTURES)

    assert strata_list_orphans(graph, "view")[0]["name"] == "orphan_view"
    assert strata_list_orphans(graph, "field") == []


def test_strata_explore_deps():
    graph = build_resolved_graph(FIXTURES)

    deps = strata_explore_deps(graph, "refined_customer", "refined_explore")

    assert deps["base_view"] == "customer_extended"
    assert deps["joins"] == [
        {"name": "simple", "view": "simple", "type": "left_outer"},
        {"name": "chain_final", "view": "chain_final", "type": "left_outer"},
    ]
    assert deps["resolution_chain"] == ["refined_customer", "+refined_customer"]
    assert deps["field_count"] == 16


def test_strata_ir_status():
    graph = build_resolved_graph(FIXTURES)
    graph.cache_path = "/tmp/strata-test.db"

    status = strata_ir_status(graph)

    assert status["repo_path"].endswith("tests/fixtures")
    assert status["node_counts"]["view"] == 9
    assert status["edge_count"] > 0
    assert status["cache_path"] == "/tmp/strata-test.db"


def test_l1_repo_brain_tools():
    from strata.l1.enrich import enrich_graph
    from strata.l1.fixtures import load_usage_facts

    graph = build_resolved_graph(FIXTURES)
    facts = load_usage_facts(FIXTURES / "usage_facts.json")
    enrich_graph(graph, facts["explore_usage"], facts["content_references"], facts["pdt_builds"])

    summary = strata_usage_summary(graph)
    assert summary["total_queries"] == 49
    assert summary["dead_code_count"] >= 2
    assert strata_dead_code_register(graph)
    assert strata_pdt_costs(graph)[0]["status"] == "unused"
    assert strata_impact(graph, "analytics.orders")["views"] == ["pdt_orders", "pdt_scope_orders"]


def test_strata_list_skills():
    skills = strata_list_skills(SKILLS_DIR)
    names = [s["name"] for s in skills]
    assert "bq_schema_probe" in names
    assert "bq_query_guardrail" in names
    assert "dashboard_composer" in names
    assert "jira_to_bi_spec" in names
    for skill in skills:
        assert "domain" in skill
        assert "mode" in skill
        assert "trigger" in skill


def test_strata_skill_returns_full_content():
    content = strata_skill(SKILLS_DIR, "bq_schema_probe")
    assert "## Procedure" in content
    assert "## Output Format" in content
    assert "bq show --schema" in content


def test_strata_skill_missing_returns_error():
    result = strata_skill(SKILLS_DIR, "nonexistent_skill")
    assert "not found" in result


def test_strata_conductor_status():
    status = strata_conductor_status(CONDUCTOR_DIR)
    assert "active_slice" in status
    assert "latest_handoff" in status
    assert len(status["latest_handoff"]) > 0


def test_strata_schema_drift_tool():
    from strata.pipeline import build_graph

    graph = build_graph(
        FIXTURES, FIXTURES / "usage_facts.json", FIXTURES / "schema_facts_drift.json"
    )
    hits = strata_schema_drift(graph)
    assert isinstance(hits, list)
    assert len(hits) > 0
    hit = hits[0]
    assert "field" in hit
    assert "table" in hit
    assert "reason" in hit


def test_strata_validation_scope_tool():
    graph = build_resolved_graph(FIXTURES)
    result = strata_validation_scope(graph, [{"kind": "view", "name": "customer_extended"}])
    assert "explores" in result
    explore_names = [e["explore"] for e in result["explores"]]
    assert "refined_customer" in explore_names


def test_strata_find_field_returns_bare_field_name():
    graph = build_resolved_graph(FIXTURES)

    result = strata_find_field(graph, "email")

    assert result["count"] >= 1
    # Regression: field must be the bare name, never view-qualified (no doubling)
    for match in result["matches"]:
        assert "." not in match["field"]
    assert "customer_extended" in {m["view"] for m in result["matches"]}


def test_navigate_brief_field_anchor_cites_source_line():
    graph = build_resolved_graph(FIXTURES)

    brief = build_navigate_brief(graph, "customer_extended.email")

    assert brief["anchor_type"] == "field"
    match = next(m for m in brief["field_matches"] if m["field"] == "email")
    assert match["source_file"] == "customer_extended.view.lkml"
    assert isinstance(match["source_line"], int)
    assert match["source_line"] >= 1


def test_navigate_brief_view_anchor_and_change_type():
    graph = build_resolved_graph(FIXTURES)

    brief = build_navigate_brief(graph, "customer_extended", ticket="add a new region dimension")

    assert brief["anchor_type"] == "view"
    names = [v["name"] for v in brief["views"]]
    assert "customer_extended" in names
    assert brief["change_type"] == "add_field"
    assert brief["what_to_touch"]


def test_navigate_brief_missing_anchor_errors():
    graph = build_resolved_graph(FIXTURES)

    brief = build_navigate_brief(graph, "no_such_field_xyz.nope")

    assert "error" in brief


def test_view_sources_carries_build_time_source_line():
    graph = build_resolved_graph(FIXTURES)

    cust = next(v for v in strata_view_sources(graph)["views"] if v["name"] == "customer_extended")

    assert isinstance(cust["source_line"], int)


def test_navigate_source_line_comes_from_ir_not_request_time(tmp_path):
    # Lines must be captured at IR build, not re-read from disk during the request
    # (MCP layer must answer from the cache and never parse raw LookML at request time).
    graph = build_resolved_graph(FIXTURES)
    graph.repo_path = str(tmp_path / "gone")  # any live file read would now fail

    brief = build_navigate_brief(graph, "customer_extended")

    v = next(v for v in brief["views"] if v["name"] == "customer_extended")
    assert isinstance(v["source_line"], int)


def test_navigate_single_token_field_anchor_resolves():
    # 'email' is a field, not a view name; classified as "view" but must fall back to find_field
    graph = build_resolved_graph(FIXTURES)

    brief = build_navigate_brief(graph, "email")

    assert brief.get("field_matches"), brief
    assert any(m["field"] == "email" for m in brief["field_matches"])


def test_navigate_unknown_single_token_errors():
    graph = build_resolved_graph(FIXTURES)

    assert "error" in build_navigate_brief(graph, "zzz_not_a_thing_anywhere")


def test_strata_chart_templates():
    charts_dir = REPO_ROOT / "src" / "strata" / "viz" / "charts"
    templates = strata_chart_templates(charts_dir)
    assert isinstance(templates, list)
    names = [t["name"] for t in templates]
    assert set(names) == {"bar", "line", "scatter", "heatmap"}
    for t in templates:
        assert "mark" in t
        assert t["mark"] in {"bar", "line", "point", "rect"}
