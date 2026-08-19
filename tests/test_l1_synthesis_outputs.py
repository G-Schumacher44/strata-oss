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
from strata.outputs.dashboard import build_dashboard_html
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


def test_graph_marks_dead_explores_dead():
    """Dead-code register names explores MODEL-QUALIFIED; graph labels are bare. A bare-name
    lookup silently missed every dead explore (rendered green/KEEP — caught regenerating the
    README screenshots, PR #21). Pin the qualified lookup, plus a live-explore negative control."""
    from strata.outputs.dashboard import _build_graph_data

    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    data = _build_graph_data(graph)
    by_id = {n["data"]["id"]: n["data"] for n in data["nodes"]}

    dead = by_id["explore:em_legacy_v2:dead_finance_v2"]
    assert dead["dead"] is True, "model-qualified dead explore must carry dead=True"
    assert dead["color"] == "#e74c3c", "dead explore must render dead-red, not active-green"

    live = by_id["explore:em_finance_base:revenue_trends"]
    assert live["dead"] is False
    assert live["color"] == "#2ecc71"


def test_view_status_credits_inherited_consumers():
    """Codex P1 (PR #25): an explore targeting a CHILD view is a consumer of every ancestor
    in the child's resolution_chain — the panel's view status must agree with the resolver's
    own _mark_orphans ancestry walk. In the fixtures, test_model.customer targets
    customer_extended, which extends base_customer: base_customer must show the inherited
    consumer and must NOT read as orphaned."""
    from strata.outputs.dashboard import _build_graph_data

    graph = build_graph(FIXTURES, FIXTURES / "usage_facts.json")
    data = _build_graph_data(graph)
    by_id = {n["data"]["id"]: n["data"] for n in data["nodes"]}

    base = by_id["view:base_customer"]
    keys = [c["key"] for c in base.get("referencing_explores", [])]
    assert "test_model.customer" in keys, f"inherited consumer missing: {keys}"
    assert base.get("status") != "orphaned", "ancestor of a targeted view must not be orphaned"

    # Negative control: a genuinely orphaned view stays orphaned.
    orphan = by_id.get("view:orphan_view")
    assert orphan is not None and orphan.get("status") == "orphaned"


def test_pdt_consumers_are_direct_not_inherited():
    """Codex round 4 (PR #25): reachability and PDT-consumption are different questions.
    An explore targeting a CHILD view keeps the parent ALIVE (ancestry map) but does NOT
    consume the parent's own PDT materialization (direct map). Pin both maps' answers for
    the fixture chain (test_model.customer -> customer_extended extends base_customer)."""
    from strata.l1.enrich import direct_view_consumers, view_consumer_map

    graph = build_graph(FIXTURES, FIXTURES / "usage_facts.json")
    ancestry = view_consumer_map(graph)
    direct = direct_view_consumers(graph)

    # Ancestry: the parent inherits the child's consumer (reachability).
    assert "test_model.customer" in ancestry.get("base_customer", [])
    # Direct: the parent has NO direct consumer — its own materialization would be unused.
    assert "test_model.customer" not in direct.get("base_customer", [])
    # The child is a direct consumer target in both maps.
    assert "test_model.customer" in direct.get("customer_extended", [])


def test_zombie_pdt_detection_enterprise_mono():
    """A PDT with real build facts backing only dead explores is 'zombie', not 'used'."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    ledger_by_view = {r["view"]: r for r in graph.metadata["l1"]["pdt_ledger"]}

    for view in ("pdt_attribution_full_funnel", "pdt_customer_value_score"):
        record = ledger_by_view[view]
        assert record["status"] == "zombie", f"{view} should be zombie, got {record['status']}"
        assert record["build_count"] > 0
        assert record["used_by_explores"], "zombie PDTs must still have consumers"
        # The zombie verdict rests on the consumers' dead-code entries — the evidence
        # trail must cite every one of them (dual-evidence contract; PR #21 Codex P2).
        for exp in record["used_by_explores"]:
            assert f"dead:explore:{exp}" in record["evidence_ids"], (
                f"{view}: zombie verdict missing dead-explore evidence for {exp}"
            )

    # A non-zombie record must NOT carry dead-explore evidence entries.
    live_records = [r for r in ledger_by_view.values() if r["status"] == "used"]
    assert live_records, "expected at least one 'used' PDT in the fixture"
    for r in live_records:
        assert not any(e.startswith("dead:explore:") for e in r["evidence_ids"]), (
            f"{r['view']}: 'used' PDT should not cite dead-explore evidence"
        )

    artifacts = build_artifacts(graph)
    html = build_dashboard_html(artifacts, graph)
    assert "zombie-badge" in html
    assert '"status": "zombie"' in html

    # Negative control: a PDT with a live consumer must not be flagged zombie.
    live_record = ledger_by_view["pdt_regional_kpi"]
    assert live_record["status"] == "used"


def test_pdt_ledger_unused_status_unaffected_by_zombie_detection():
    """A PDT with zero consumers stays 'unused' — distinct from 'zombie' (dead consumers)."""
    GCS = ROOT / "tests" / "lookml" / "gcs_analytics"
    USAGE = ROOT / "tests" / "fixtures" / "gcs_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "gcs_schema_facts.json"
    graph = build_graph(GCS, USAGE, SCHEMA)
    ledger_by_view = {r["view"]: r for r in graph.metadata["l1"]["pdt_ledger"]}
    assert ledger_by_view["pdt_retention_signals"]["status"] == "unused"
    assert ledger_by_view["pdt_retention_signals"]["used_by_explores"] == []


def test_graph_node_detail_carries_pdt_ledger_fields():
    """Node-detail panel data (dashboard PR #23) — PDT nodes must carry the full ledger
    record, not just name/kind/source, so the graph click isn't an anticlimax. Both
    fixture zombies + a negative-control 'used' PDT, since the color/status mapping
    branches on status."""
    from strata.outputs.dashboard import _build_graph_data

    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    data = _build_graph_data(graph)
    by_id = {n["data"]["id"]: n["data"] for n in data["nodes"]}

    for pdt_id, view in (
        ("pdt:pdt_attribution_full_funnel", "pdt_attribution_full_funnel"),
        ("pdt:pdt_customer_value_score", "pdt_customer_value_score"),
    ):
        d = by_id[pdt_id]
        assert d["status"] == "zombie"
        assert d["color"] == "#9b59b6"
        assert d["estimated_cost_usd"] > 0
        assert d["build_count"] > 0
        assert d["bytes_processed"] > 0
        assert d["used_by_explores"], f"{view}: zombie PDT must list its consumers"
        assert all(c["dead"] for c in d["used_by_explores"])

    # Negative control: a real 'used' PDT must not be flagged zombie/unused, and its
    # consumers must not be mismarked dead.
    live = by_id["pdt:pdt_regional_kpi"]
    assert live["status"] == "used"
    assert live["color"] == "#2ecc71"
    assert live["used_by_explores"]
    assert not any(c["dead"] for c in live["used_by_explores"])


def test_graph_node_detail_status_vocabulary_per_kind():
    """Status vocabulary (dashboard PR #23) — PDT/explore/view nodes carry the honest
    three-way zombie vocabulary instead of a flattened DEAD/ORPHAN flag, with colors
    matching the legend."""
    from strata.outputs.dashboard import _build_graph_data

    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    data = _build_graph_data(graph)
    by_id = {n["data"]["id"]: n["data"] for n in data["nodes"]}

    # PDT: zombie / used already covered above; explore verdict vocabulary here.
    dead_explore = by_id["explore:em_legacy_v2:dead_finance_v2"]
    assert dead_explore["dead"] is True
    live_explore = by_id["explore:em_finance_base:revenue_trends"]
    assert live_explore["dead"] is False

    # View: zombie view (real edges, all-dead consumers) vs. active — distinct from a
    # true orphan (no explore reference at all) even though both are flagged `dead`.
    zombie_view = by_id["view:legacy_order_detail"]
    assert zombie_view["status"] == "zombie_view"
    assert zombie_view["color"] == "#9b59b6"
    assert zombie_view["referencing_explores"], (
        "zombie view must be referenced, not structurally orphaned"
    )
    assert all(c["dead"] for c in zombie_view["referencing_explores"])

    active_view = by_id["view:fct_cart_abandonment"]
    assert active_view["status"] == "active"
    assert active_view["color"] == "#3498db"

    # True orphan (no explore reference at all) is a distinct third state — pull from
    # the smaller FIXTURES set, which has a genuine orphan.
    fixtures_graph = build_graph(FIXTURES, FIXTURES / "usage_facts.json")
    fixtures_data = _build_graph_data(fixtures_graph)
    fixtures_by_id = {n["data"]["id"]: n["data"] for n in fixtures_data["nodes"]}
    orphan_view = fixtures_by_id["view:orphan_view"]
    assert orphan_view["status"] == "orphaned"
    assert orphan_view["color"] == "#95a5a6"
    assert orphan_view["referencing_explores"] == []


def test_graph_node_pdt_dependencies_and_table_references():
    """Explore -> PDT dependency and physical-table -> referencing-view data (dashboard
    PR #23), derived from the graph edges rather than invented."""
    from strata.outputs.dashboard import _build_graph_data

    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    data = _build_graph_data(graph)
    by_id = {n["data"]["id"]: n["data"] for n in data["nodes"]}

    dead_finance = by_id["explore:em_legacy_v2:dead_finance_v2"]
    assert "pdt_attribution_full_funnel" in dead_finance["pdt_dependencies"]

    table = by_id["physical_table:acme-analytics.gold_marts.fct_cart_abandonment"]
    assert table["referencing_views"] == ["fct_cart_abandonment"]


def test_schema_drift_rows_differ_by_field_not_true_duplicates():
    """Schema Drift dedup arithmetic (dashboard PR #23) — rows that look byte-identical
    on kind/table/column/source_file/reason actually differ by `field` (the LookML field
    whose SQL references the drifted column). Pin that assumption: it's why the dashboard
    surfaces the Field column instead of collapsing genuinely distinct issues under a
    fake ×N dedup."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    artifacts = build_artifacts(graph)
    drift = artifacts["schema_drift"]
    assert len(drift) > 0

    visible_keys = {
        (r["kind"], r["table"], r.get("column"), r["source_file"], r["reason"]) for r in drift
    }
    full_keys = {
        (r["kind"], r["table"], r.get("column"), r.get("field"), r["source_file"], r["reason"])
        for r in drift
    }
    assert len(visible_keys) < len(drift), (
        "fixture must reproduce the apparent-duplicate rows this fix addresses"
    )
    assert len(full_keys) == len(drift), (
        "rows differ by `field` — every row is a genuinely distinct issue once field is shown"
    )

    html = build_dashboard_html(artifacts, graph)
    assert "<th>Field</th>" in html
    assert "legacy_order_detail.total_unit_cost" in html


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
