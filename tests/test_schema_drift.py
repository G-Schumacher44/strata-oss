from pathlib import Path

from strata.ir.resolver import build_resolved_graph
from strata.l1.schema import FixtureSchemaProvider, enrich_schema_drift, load_schema_facts
from strata.mcp.tools import strata_schema_drift, strata_usage_summary
from strata.outputs import build_artifacts
from strata.pipeline import build_graph

FIXTURES = Path(__file__).parent / "fixtures"


def test_fixture_schema_provider_loads_tables():
    facts = load_schema_facts(FIXTURES / "schema_facts_clean.json")

    assert len(facts.tables) == 6
    assert (
        FixtureSchemaProvider(FIXTURES / "schema_facts_clean.json").tables()[0].name
        == "analytics.chain_base"
    )


def test_schema_drift_detects_missing_table_and_column():
    graph = build_resolved_graph(FIXTURES)
    enrich_schema_drift(graph, load_schema_facts(FIXTURES / "schema_facts_drift.json"))

    records = graph.metadata["l1"]["schema_drift"]
    ids = {record["id"] for record in records}

    assert "schema:missing_table:analytics.orphan_view" in ids
    assert (
        "schema:missing_column:analytics.customer_snapshot.segment:customer_extended.segment" in ids
    )
    assert "schema:missing_column:analytics.chain_base.final_only:chain_final.final_only" in ids
    assert all(record["evidence_ids"] for record in records)


def test_clean_schema_fixture_produces_no_drift():
    graph = build_resolved_graph(FIXTURES)
    enrich_schema_drift(graph, load_schema_facts(FIXTURES / "schema_facts_clean.json"))

    assert graph.metadata["l1"]["schema_drift"] == []


def test_schema_drift_surfaces_in_pipeline_artifacts_and_mcp():
    graph = build_graph(
        FIXTURES,
        usage_fixture=FIXTURES / "usage_facts.json",
        schema_fixture=FIXTURES / "schema_facts_drift.json",
    )

    records = strata_schema_drift(graph)
    artifacts = build_artifacts(graph)

    assert records == graph.metadata["l1"]["schema_drift"]
    assert artifacts["schema_drift"] == records
    assert strata_usage_summary(graph)["schema_drift_count"] == len(records)
    assert any(item["action"] == "repair_schema_reference" for item in artifacts["cleanup_roadmap"])
