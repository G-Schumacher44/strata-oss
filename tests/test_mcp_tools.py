from pathlib import Path

import pytest

from strata_lookml.errors import InvalidInput, NotFound
from strata_lookml.ir.resolver import build_resolved_graph
from strata_lookml.mcp.tools import (
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
from strata_lookml.navigate import _classify_anchor, build_navigate_brief

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "src" / "strata_lookml" / "skills"

FIXTURES = Path(__file__).parent / "fixtures"
# Use a committed fixture, not the live repo conductor/, so the test is
# deterministic and doesn't depend on in-flight slice/handoff state.
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
    assert strata_list_orphans(graph, "all") == strata_list_orphans(graph, "view")


@pytest.mark.parametrize("kind", ["explore", "field", "bogus"])
def test_strata_list_orphans_rejects_unsupported_kind(kind):
    # Only view orphans are detected; an empty [] for explore/field would read as "none exist".
    graph = build_resolved_graph(FIXTURES)

    with pytest.raises(InvalidInput, match="only orphan views are detected"):
        strata_list_orphans(graph, kind)


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
    from strata_lookml.l1.enrich import enrich_graph
    from strata_lookml.l1.fixtures import load_usage_facts

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


def test_strata_skill_missing_raises_not_found_listing_skills():
    with pytest.raises(NotFound, match="skill not found") as err:
        strata_skill(SKILLS_DIR, "nonexistent_skill")
    assert "lookml_ticket_navigator" in (err.value.hint or "")


def test_strata_conductor_status():
    status = strata_conductor_status(CONDUCTOR_DIR)
    assert "active_slice" in status
    assert "latest_handoff" in status
    assert len(status["latest_handoff"]) > 0


def test_strata_schema_drift_tool():
    from strata_lookml.pipeline import build_graph

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

    with pytest.raises(NotFound, match="No fields matching"):
        build_navigate_brief(graph, "no_such_field_xyz.nope")


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

    with pytest.raises(NotFound, match="No view, explore, or field"):
        build_navigate_brief(graph, "zzz_not_a_thing_anywhere")


def test_strata_chart_templates():
    charts_dir = REPO_ROOT / "src" / "strata_lookml" / "viz" / "charts"
    templates = strata_chart_templates(charts_dir)
    assert isinstance(templates, list)
    names = [t["name"] for t in templates]
    assert set(names) == {"bar", "line", "scatter", "heatmap"}
    for t in templates:
        assert "mark" in t
        assert t["mark"] in {"bar", "line", "point", "rect"}


def test_strata_find_field_truncated_flag_absent_when_under_cap():
    graph = build_resolved_graph(FIXTURES)
    result = strata_find_field(graph, "")
    assert result["count"] < 50
    assert result["truncated"] is False


def test_strata_find_field_truncated_flag_present_at_cap():
    from strata_lookml.ir.types import IRGraph, IRNode

    # Build a synthetic graph with 51 matching field nodes to trigger the cap.
    graph = IRGraph(repo_path="/synthetic", built_at="2026-01-01T00:00:00+00:00")
    for i in range(51):
        node_id = f"field:big_view.metric_{i:03d}"
        graph.add_node(
            IRNode(
                id=node_id,
                kind="field",
                name=f"big_view.metric_{i:03d}",
                source_file="big_view.view.lkml",
                attrs={
                    "field_kind": "measure",
                    "view": "big_view",
                    "field_name": f"metric_{i:03d}",
                },
            )
        )

    result = strata_find_field(graph, "metric")
    assert result["count"] == 50
    assert result["truncated"] is True


def test_strata_find_field_truncated_flag_false_at_exactly_fifty_matches():
    from strata_lookml.ir.types import IRGraph, IRNode

    # Exactly 50 matching field nodes: all 50 are returned, nothing is omitted,
    # so truncated must be False. This is the off-by-one boundary: len(matches)
    # can never exceed the 50 cap, so `len(matches) >= 50` wrongly reports
    # truncated=True here even though nothing was cut.
    graph = IRGraph(repo_path="/synthetic", built_at="2026-01-01T00:00:00+00:00")
    for i in range(50):
        node_id = f"field:big_view.metric_{i:03d}"
        graph.add_node(
            IRNode(
                id=node_id,
                kind="field",
                name=f"big_view.metric_{i:03d}",
                source_file="big_view.view.lkml",
                attrs={
                    "field_kind": "measure",
                    "view": "big_view",
                    "field_name": f"metric_{i:03d}",
                },
            )
        )

    result = strata_find_field(graph, "metric")
    assert result["count"] == 50
    assert result["truncated"] is False


def test_navigate_two_part_anchor_resolves_to_physical_table_when_in_ir():
    # Regression: `dataset.table` was always classified as a field and substring-searched.
    from strata_lookml.ir.types import IRGraph, IRNode

    graph = IRGraph(repo_path="", built_at="")
    graph.add_node(
        IRNode(
            id="physical_table:analytics.orders",
            kind="physical_table",
            name="analytics.orders",
            source_file="",
        )
    )
    brief = build_navigate_brief(graph, "analytics.orders")
    assert brief["anchor_type"] == "bq_table"
    # A two-part anchor that is not a known table still falls through to field lookup.
    assert _classify_anchor("orders.id", graph) == "field"


def test_navigate_two_part_anchor_prefers_exact_field_over_same_named_table():
    # Regression (#38 review): with both `physical_table:analytics.orders` and
    # `field:analytics.orders` in the IR, the field anchor was shadowed by the table.
    from strata_lookml.ir.types import IRGraph, IRNode

    graph = IRGraph(repo_path="", built_at="")
    graph.add_node(
        IRNode("physical_table:analytics.orders", "physical_table", "analytics.orders", "")
    )
    graph.add_node(
        IRNode(
            "field:analytics.orders",
            "field",
            "analytics.orders",
            "",
            attrs={"view": "analytics", "field_name": "orders", "field_kind": "dimension"},
        )
    )
    brief = build_navigate_brief(graph, "analytics.orders")
    assert brief["anchor_type"] == "field"
    assert [m["field"] for m in brief["field_matches"]] == ["orders"]
    assert "ambiguous_anchor" in brief


def test_load_ir_missing_cache_raises_without_creating_a_file(tmp_path):
    import pytest

    from strata_lookml.ir.store import load_ir

    missing = tmp_path / "strata_ir.db"
    with pytest.raises(FileNotFoundError, match="IR cache not found"):
        load_ir(missing)
    assert not missing.exists()


def test_load_ir_open_cannot_create_the_cache_even_if_exists_check_races(tmp_path, monkeypatch):
    # Regression (#39 review): exists() then sqlite3.connect raced a concurrent `strata clean`;
    # the connect recreated the ghost file. Simulate the race by making exists() lie.
    import os
    import sqlite3

    import pytest

    from strata_lookml.ir.store import cache_age_seconds, load_ir

    missing = tmp_path / "strata_ir.db"
    monkeypatch.setattr(Path, "exists", lambda self: True)
    with pytest.raises((FileNotFoundError, sqlite3.OperationalError)):
        load_ir(missing)
    assert cache_age_seconds(missing) is None  # an unopenable cache is a miss, not a crash
    assert not os.path.exists(missing)


def test_ir_cache_roundtrips_through_a_path_needing_uri_escaping(tmp_path):
    from strata_lookml.ir.store import cache_age_seconds, load_ir, save_ir
    from strata_lookml.ir.types import IRGraph

    cache = tmp_path / "dir with space #1 ?x" / "strata_ir.db"
    save_ir(IRGraph(repo_path="r", built_at="2026-01-01T00:00:00+00:00"), cache)
    assert load_ir(cache).repo_path == "r"
    assert cache_age_seconds(cache) is not None
    assert cache_age_seconds(tmp_path / "nope.db") is None
    assert not (tmp_path / "nope.db").exists()


def test_rebuild_picks_up_edited_source_lines(tmp_path):
    # Regression: _scan_file's process-wide lru_cache served the first build's line numbers
    # to every later build in the same process.
    (tmp_path / "v.view.lkml").write_text(
        "view: orders {\n  dimension: id {\n    type: number\n  }\n}\n", encoding="utf-8"
    )
    first = build_resolved_graph(tmp_path).nodes["view:orders"].attrs["source_line"]
    (tmp_path / "v.view.lkml").write_text(
        "# header\n# header\n" + (tmp_path / "v.view.lkml").read_text()
    )
    second = build_resolved_graph(tmp_path).nodes["view:orders"].attrs["source_line"]
    assert (first, second) == (1, 3)
