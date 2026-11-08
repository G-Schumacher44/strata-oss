"""MCP response envelope and agent-facing descriptions (S2), over the real server + client."""

import asyncio
import json
from pathlib import Path

import pytest
from mcp import Client

from strata_lookml.ir.resolver import build_resolved_graph
from strata_lookml.mcp.server import create_server
from strata_lookml.pipeline import build_graph

ROOT = Path(__file__).resolve().parents[1]
GCS = ROOT / "tests" / "lookml" / "gcs_analytics"
USAGE = ROOT / "tests" / "fixtures" / "gcs_usage_facts.json"
SCHEMA = ROOT / "tests" / "fixtures" / "gcs_schema_facts.json"
FIXTURES = Path(__file__).parent / "fixtures"

LIST_TOOLS = [
    "strata_list_orphans",
    "strata_dead_code_register",
    "strata_pdt_costs",
    "strata_schema_drift",
    "strata_list_skills",
    "strata_chart_templates",
]


def _session(graph, fn):
    async def run():
        async with Client(create_server(graph)) as client:
            return await fn(client)

    return asyncio.run(run())


def _call(graph, name, arguments=None):
    return _session(graph, lambda c: c.call_tool(name, arguments or {}))


def _payload(result):
    assert len(result.content) == 1, "one JSON block, not one block per item"
    return json.loads(result.content[0].text)


def test_every_tool_parameter_is_described():
    tools = _session(build_resolved_graph(FIXTURES), lambda c: c.list_tools()).tools
    undescribed = [
        f"{tool.name}.{prop}"
        for tool in tools
        for prop, schema in (tool.input_schema or {}).get("properties", {}).items()
        if not schema.get("description")
    ]
    assert not undescribed, f"parameters without a description: {undescribed}"


def test_server_instructions_are_set_and_name_the_fixture_env_vars():
    graph = build_resolved_graph(FIXTURES)
    instructions = create_server(graph).instructions
    assert instructions and "strata_navigate" in instructions
    assert "STRATA_USAGE_FIXTURE" in instructions and "STRATA_SCHEMA_FIXTURE" in instructions


@pytest.mark.parametrize("name", LIST_TOOLS)
def test_list_tools_return_one_items_count_object(name):
    data = _payload(_call(build_resolved_graph(FIXTURES), name))
    assert isinstance(data["items"], list)
    assert data["count"] == len(data["items"])


def test_list_tools_with_items_are_still_a_single_block():
    # The failure being fixed: a bare list is split into one content block per element.
    graph = build_resolved_graph(FIXTURES)
    assert _payload(_call(graph, "strata_list_skills"))["count"] > 1
    assert _payload(_call(graph, "strata_chart_templates"))["count"] > 1


def test_l1_list_tools_flag_unchecked_and_name_the_env_var():
    graph = build_resolved_graph(FIXTURES)
    for name, flag, env in [
        ("strata_dead_code_register", "usage_checked", "STRATA_USAGE_FIXTURE"),
        ("strata_pdt_costs", "usage_checked", "STRATA_USAGE_FIXTURE"),
        ("strata_schema_drift", "schema_checked", "STRATA_SCHEMA_FIXTURE"),
    ]:
        data = _payload(_call(graph, name))
        assert data["items"] == [] and data[flag] is False
        assert env in data["hint"]


def test_l1_list_tools_checked_have_no_hint():
    graph = build_graph(GCS, USAGE, SCHEMA)
    dead = _payload(_call(graph, "strata_dead_code_register"))
    assert dead["usage_checked"] is True and dead["count"] > 0 and "hint" not in dead
    drift = _payload(_call(graph, "strata_schema_drift"))
    assert drift["schema_checked"] is True and "hint" not in drift


def test_usage_summary_without_fixtures_reports_nothing_checked():
    data = _payload(_call(build_resolved_graph(FIXTURES), "strata_usage_summary"))
    assert (data["usage_checked"], data["schema_checked"]) == (False, False)
    assert "STRATA_USAGE_FIXTURE" in data["hint"] and "STRATA_SCHEMA_FIXTURE" in data["hint"]


def test_usage_summary_schema_only_build_is_not_usage_checked():
    # N6: a schema-only build creates the l1 block, so the old has_l1 was true with
    # dead_code_count 0, reading as "usage checked, nothing dead".
    data = _payload(_call(build_graph(GCS, None, SCHEMA), "strata_usage_summary"))
    assert data["usage_checked"] is False and data["schema_checked"] is True
    assert data["has_l1"] is True  # deprecated: any L1 data
    assert "STRATA_USAGE_FIXTURE" in data["hint"] and "STRATA_SCHEMA_FIXTURE" not in data["hint"]


def test_usage_summary_fully_checked_has_no_hint():
    data = _payload(_call(build_graph(GCS, USAGE, SCHEMA), "strata_usage_summary"))
    assert (data["usage_checked"], data["schema_checked"]) == (True, True)
    assert data["hint"] is None


def test_find_field_limit_caps_and_flags_truncation():
    graph = build_resolved_graph(FIXTURES)
    wide = _payload(_call(graph, "strata_find_field", {"query": "id", "limit": 200}))
    assert wide["count"] > 1
    capped = _payload(_call(graph, "strata_find_field", {"query": "id", "limit": 1}))
    assert capped["count"] == 1 and capped["truncated"] is True


@pytest.mark.parametrize("arguments", [{"query": "id", "limit": 201}, {"query": "id", "limit": 0}])
def test_find_field_rejects_out_of_range_limit(arguments):
    assert _call(build_resolved_graph(FIXTURES), "strata_find_field", arguments).is_error is True


def test_find_field_rejects_one_character_query():
    result = _call(build_resolved_graph(FIXTURES), "strata_find_field", {"query": "i"})
    assert result.is_error is True
