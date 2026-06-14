import json
import subprocess
import sys
from pathlib import Path

import pytest

from strata.l1.enrich import enrich_graph
from strata.l1.fixtures import load_usage_facts
from strata.l1.types import ExploreUsage
from strata.mcp.tools import strata_impact
from strata.outputs import build_artifacts, write_artifacts
from strata.pipeline import build_graph
from strata.synthesis.slices import build_explore_slice
from strata.synthesis.verdicts import SynthesisVerdict, deterministic_verdict, validate_verdict

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def test_l1_enrichment_static_usage_intersection_and_pdt_ledger():
    graph = build_graph(FIXTURES)
    facts = load_usage_facts(FIXTURES / "usage_facts.json")

    enrich_graph(graph, facts["explore_usage"], facts["content_references"], facts["pdt_builds"])

    dead_names = {record["name"] for record in graph.metadata["l1"]["dead_code"]}
    assert {"orphan_view", "pdt_orders", "test_model.orphan_explore"} <= dead_names
    pdt = graph.metadata["l1"]["pdt_ledger"][0]
    assert pdt["view"] == "pdt_orders"
    assert pdt["estimated_cost_usd"] == 6.5
    assert pdt["status"] == "unused"


def test_synthesis_slice_and_evidence_validation():
    graph = build_graph(FIXTURES, FIXTURES / "usage_facts.json")

    explore_slice = build_explore_slice(graph, "test_model", "orphan_explore")
    verdict = deterministic_verdict(explore_slice)

    assert verdict.verdict == "deprecate"
    assert validate_verdict(verdict, explore_slice["evidence_ids"]) == []
    bad = SynthesisVerdict(explore_slice["id"], "kill", "missing trail", [])
    assert validate_verdict(bad, explore_slice["evidence_ids"])


def test_review_patch_guardrails(tmp_path):
    facts_json = tmp_path / "usage_extra.json"
    facts_json.write_text(
        json.dumps(
            {
                "explore_usage": [
                    {
                        "model": "test_model",
                        "explore": "orphan_explore",
                        "query_count": 0,
                        "last_queried_at": None,
                        "future_column": "ignored",
                    }
                ],
                "content_references": [],
                "pdt_builds": [],
            }
        ),
        encoding="utf-8",
    )
    facts = load_usage_facts(facts_json)
    assert facts["explore_usage"] == [ExploreUsage("test_model", "orphan_explore", 0, None)]

    graph = build_graph(FIXTURES)
    enrich_graph(graph, facts["explore_usage"], [], [])
    with pytest.raises(RuntimeError):
        enrich_graph(graph, facts["explore_usage"], [], [])

    missing_usage_graph = build_graph(FIXTURES)
    enrich_graph(missing_usage_graph, [], [], [])
    assert "test_model.customer" in {
        record["name"] for record in missing_usage_graph.metadata["l1"]["dead_code"]
    }

    unknown_content_graph = build_graph(FIXTURES)
    enrich_graph(
        unknown_content_graph, facts["explore_usage"], content_references=None, pdt_builds=[]
    )
    assert "test_model.orphan_explore" not in {
        record["name"] for record in unknown_content_graph.metadata["l1"]["dead_code"]
    }

    enriched = build_graph(FIXTURES, FIXTURES / "usage_facts.json")
    assert build_explore_slice(enriched, "test_model", "orphan_explore")["pdt_evidence"] == []
    result = strata_impact(enriched, "analytics.missing_table")
    assert "error" in result

    keep = deterministic_verdict(build_explore_slice(enriched, "test_model", "customer"))
    assert keep.verdict == "keep"
    assert validate_verdict(keep, []) == []

    orphan_slice = build_explore_slice(enriched, "test_model", "orphan_explore")
    partial = SynthesisVerdict(
        orphan_slice["id"],
        "deprecate",
        "partial evidence",
        orphan_slice["evidence_ids"][:1],
    )
    assert validate_verdict(partial, orphan_slice["evidence_ids"])


def test_output_artifacts_are_deterministic(tmp_path):
    graph = build_graph(FIXTURES, FIXTURES / "usage_facts.json")

    artifacts = build_artifacts(graph)
    written = write_artifacts(graph, tmp_path)

    assert {
        "catalog",
        "dead_code_register",
        "pdt_ledger",
        "cleanup_roadmap",
        "migration_impact",
    } <= set(artifacts)
    assert Path(written["dead_code_register"]).exists()
    loaded = json.loads(Path(written["pdt_ledger"]).read_text(encoding="utf-8"))
    assert loaded[0]["view"] == "pdt_orders"


def test_zombie_view_detection_enterprise_mono():
    """Views referenced exclusively by dead explores must surface in dead_code_register."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    dead = graph.metadata["l1"]["dead_code"]
    dead_by_name = {item["name"]: item for item in dead}

    # These three legacy views are only backed by dead explores — zombie views
    for view_name in (
        "legacy_customer_profile",
        "legacy_inventory_snapshot",
        "legacy_order_detail",
    ):
        assert view_name in dead_by_name, f"zombie view not detected: {view_name}"
        item = dead_by_name[view_name]
        assert item["kind"] == "view"
        assert "all referencing explores" in item["usage_reason"]
        # Evidence chain must include at least one dead explore reference
        assert any("dead:explore:" in eid for eid in item["evidence_ids"])

    # Orphan views must NOT be flagged as zombie views (different detection path)
    for item in dead:
        if item["kind"] == "view" and "all referencing explores" in item["usage_reason"]:
            # Zombie view must have had at least one explore reference
            assert any("dead:explore:" in eid for eid in item["evidence_ids"])


def test_strata_gate_script_and_output_cli(tmp_path):
    gate = subprocess.run(
        [
            sys.executable,
            "-m",
            "strata.cli.main",
            "check",
            "--repo",
            str(FIXTURES),
            "--usage-fixture",
            str(FIXTURES / "usage_facts.json"),
            "--schema-fixture",
            str(FIXTURES / "schema_facts_drift.json"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert gate.returncode == 0, gate.stderr

    out = tmp_path / "artifacts"
    generated = subprocess.run(
        [
            sys.executable,
            "-m",
            "strata.cli.main",
            "outputs",
            "--repo",
            str(FIXTURES),
            "--usage-fixture",
            str(FIXTURES / "usage_facts.json"),
            "--out",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert generated.returncode == 0, generated.stderr
    assert (out / "cleanup_roadmap.json").exists()
