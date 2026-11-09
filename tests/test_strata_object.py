"""strata_object: one read per object, identical over MCP and the CLI, agreeing with the
explore_deps / impact reads it reuses."""

import asyncio
import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from mcp import Client

from strata_lookml.cli.main import strata_cli
from strata_lookml.errors import InvalidInput, NotFound
from strata_lookml.ir.resolver import build_resolved_graph
from strata_lookml.mcp.server import create_server
from strata_lookml.mcp.tools import strata_explore_deps, strata_impact, strata_object
from strata_lookml.pipeline import build_graph

ROOT = Path(__file__).resolve().parent
MONO = ROOT / "lookml" / "enterprise_mono"
TWIN = ROOT / "lookml" / "twin_models"
USAGE = ROOT / "fixtures" / "enterprise_usage_facts.json"
SCHEMA = ROOT / "fixtures" / "enterprise_schema_facts.json"

CASES = [
    ("explore", "em_executive_base.executive_summary"),
    ("view", "fct_daily_dashboard"),
    ("pdt", "pdt_attribution_full_funnel"),
    ("table", "acme-analytics.gold_marts.fct_daily_dashboard"),
    ("field", "fct_cart_abandonment.cart_date"),
]


@pytest.fixture(scope="module")
def graph():
    return build_graph(MONO, USAGE, SCHEMA)


def _mcp(graph, kind, name):
    async def call():
        async with Client(create_server(graph)) as client:
            result = await client.call_tool("strata_object", {"kind": kind, "name": name})
            return json.loads(result.content[0].text)

    return asyncio.run(call())


def _cli(kind, name):
    result = CliRunner().invoke(
        strata_cli,
        [
            "query", "object", kind, name,
            "--repo", str(MONO),
            "--usage-fixture", str(USAGE),
            "--schema-fixture", str(SCHEMA),
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


@pytest.mark.parametrize(("kind", "name"), CASES)
def test_cli_and_mcp_return_the_same_object(graph, kind, name):
    result = strata_object(graph, kind, name)
    assert result["kind"] == kind
    assert set(result) >= {
        "id", "name", "source_file", "source_line", "upstream", "downstream",
        "findings", "coverage", "content",
    }  # fmt: skip
    assert _mcp(graph, kind, name) == result
    assert _cli(kind, name) == result


def test_explore_lineage_agrees_with_explore_deps(graph):
    result = strata_object(graph, "explore", "em_executive_base.executive_summary")
    deps = strata_explore_deps(graph, "executive_summary", "em_executive_base")
    assert result["upstream"]["base_view"] == [deps["base_view"]]
    assert result["upstream"]["joined_view"] == sorted({j["view"] for j in deps["joins"]})
    assert result["details"]["joins"] == deps["joins"]
    assert result["details"]["field_count"] == deps["field_count"]


def test_table_downstream_equals_impact(graph):
    table = "acme-analytics.gold_marts.fct_daily_dashboard"
    impact = strata_impact(graph, table)
    result = strata_object(graph, "table", table)
    assert result["downstream"] == {k: impact[k] for k in ("views", "explores", "fields")}
    assert result["downstream"]["views"]


def test_live_explore_has_content_counts_with_an_honest_window(graph):
    content = strata_object(graph, "explore", "em_executive_base.executive_summary")["content"]
    assert content["reference_count"] == 1
    assert content["by_type"] == {"dashboard": 1}
    assert content["window"]["days"] == 30
    assert content["window_label"] == "viewed in 30d"


def test_dead_explore_has_zero_content_and_its_finding(graph):
    result = strata_object(graph, "explore", "em_legacy_v2.dead_finance_v2")
    assert result["content"]["reference_count"] == 0
    assert result["findings"] == ["dead:explore:em_legacy_v2.dead_finance_v2"]


def test_pdt_carries_its_finding_and_ledger(graph):
    result = strata_object(graph, "pdt", "pdt_attribution_full_funnel")
    assert result["findings"] == ["pdt:pdt_attribution_full_funnel"]
    assert result["details"]["ledger"]["status"] == "zombie"
    assert result["content"] is None


def test_without_usage_content_is_null_and_flagged():
    unenriched = build_resolved_graph(MONO)
    result = strata_object(unenriched, "explore", "em_executive_base.executive_summary")
    assert result["content"] is None
    assert result["coverage"] == {"usage_checked": False, "schema_checked": False}
    assert result["findings"] == []


def test_ambiguous_explore_lists_candidates_and_unknowns_are_not_found():
    twin = build_resolved_graph(TWIN)
    with pytest.raises(InvalidInput, match=r"retail\.orders, wholesale\.orders"):
        strata_object(twin, "explore", "orders")
    assert strata_object(twin, "explore", "wholesale.orders")["name"] == "wholesale.orders"
    for kind, name in [("explore", "nope"), ("view", "nope"), ("pdt", "nope"),
                       ("table", "nope"), ("field", "orders.nope")]:  # fmt: skip
        with pytest.raises(NotFound):
            strata_object(twin, kind, name)
    with pytest.raises(InvalidInput, match="kind must be one of"):
        strata_object(twin, "model", "x")


def test_every_mcp_parameter_is_described():
    tools = asyncio.run(create_server(build_resolved_graph(TWIN)).list_tools())
    tool = next(t for t in tools if t.name == "strata_object")
    props = tool.input_schema["properties"]
    assert set(props) == {"kind", "name"}
    assert all(p.get("description") for p in props.values())
    assert tool.annotations.read_only_hint is True


def test_schema_drift_lands_on_its_field_and_table(graph):
    field = strata_object(graph, "field", "legacy_order_detail.total_unit_cost")
    assert field["findings"] == [
        "schema:missing_column:acme-analytics.silver.int_attributed_purchases.unit_cost_usd"
        ":legacy_order_detail.total_unit_cost"
    ]
    table = strata_object(graph, "table", "acme-analytics.silver.int_attributed_purchases")
    assert field["findings"][0] in table["findings"]


def test_refined_view_does_not_list_itself_as_an_ancestor(tmp_path):
    (tmp_path / "base.view.lkml").write_text("view: base { dimension: id {} }\n")
    (tmp_path / "orders.view.lkml").write_text(
        "view: orders { extends: [base] dimension: a {} }\n"
        "view: +orders { dimension: b {} }\n"
        "view: +orders { dimension: c {} }\n"
    )
    (tmp_path / "m.model.lkml").write_text("explore: orders {}\n")
    graph = build_resolved_graph(tmp_path)
    chain = graph.nodes["view:orders"].attrs["resolution_chain"]
    assert any(c.startswith("+") for c in chain)  # the fixture really is a refined view
    assert strata_object(graph, "view", "orders")["upstream"]["extends"] == ["base"]
    assert strata_object(graph, "view", "base")["upstream"]["extends"] == []


def test_findings_land_on_their_subject_node(graph):
    from strata_lookml.gate import finding_records

    landed = 0
    for r in finding_records(graph):
        node = graph.get_node(r["subject_id"]) if r["subject_id"] else None
        assert node is not None, r["id"]
        kind = {"physical_table": "table"}.get(node.kind, node.kind)
        name = f"{node.attrs['model']}.{node.name}" if kind == "explore" else node.name
        assert r["id"] in strata_object(graph, kind, name)["findings"], r["id"]
        landed += 1
    assert landed
