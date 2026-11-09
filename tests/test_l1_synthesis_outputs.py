import json
import subprocess
import sys
from pathlib import Path

import pytest

from strata_lookml.errors import NotFound
from strata_lookml.l1.enrich import enrich_graph
from strata_lookml.l1.fixtures import load_usage_facts
from strata_lookml.l1.types import ExploreUsage
from strata_lookml.mcp.tools import strata_impact
from strata_lookml.outputs import build_artifacts, write_artifacts
from strata_lookml.pipeline import build_graph
from strata_lookml.synthesis.slices import build_explore_slice
from strata_lookml.synthesis.verdicts import (
    SynthesisVerdict,
    deterministic_verdict,
    validate_verdict,
)
from strata_lookml.workbench.graph import NODE_PALETTE
from strata_lookml.workbench.graph import build_graph_data as _build_graph_data

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
    with pytest.raises(NotFound, match="physical_table not found"):
        strata_impact(enriched, "analytics.missing_table")

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
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    data = _build_graph_data(graph)
    by_id = {n["data"]["id"]: n["data"] for n in data["nodes"]}

    dead = by_id["explore:em_legacy_v2:dead_finance_v2"]
    assert dead["dead"] is True, "model-qualified dead explore must carry dead=True"
    assert dead["color"] == NODE_PALETTE["explore_dead"], (
        "dead explore must render dead-red, not active-green"
    )

    live = by_id["explore:em_finance_base:revenue_trends"]
    assert live["dead"] is False
    assert live["color"] == NODE_PALETTE["explore_active"]


def test_view_status_credits_inherited_consumers():
    """Codex P1 (PR #25): an explore targeting a CHILD view is a consumer of every ancestor
    in the child's resolution_chain — the panel's view status must agree with the resolver's
    own _mark_orphans ancestry walk. In the fixtures, test_model.customer targets
    customer_extended, which extends base_customer: base_customer must show the inherited
    consumer and must NOT read as orphaned."""
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


def test_physical_table_panel_counts_pdt_upstream_references():
    """Codex r5 (PR #25): derived-table SQL references (pdt→upstream) must appear in the
    physical-table panel's referencing list, mirroring strata_impact()'s mapping — the
    panel must never undercount the references a deletion would break."""
    graph = build_graph(FIXTURES, FIXTURES / "usage_facts.json")
    # ground truth: which tables have pdt→upstream edges in the fixture graph
    upstream = {}
    for e in graph.edges:
        if e.relation == "pdt→upstream" and e.target.startswith("physical_table:"):
            n = graph.nodes.get(e.source)
            if n:
                upstream.setdefault(e.target.removeprefix("physical_table:"), set()).add(n.name)
    assert upstream, "fixtures must exercise at least one pdt→upstream edge"

    data = _build_graph_data(graph)
    by_id = {n["data"]["id"]: n["data"] for n in data["nodes"]}
    for table, expected in upstream.items():
        node = by_id.get(f"physical_table:{table}")
        assert node is not None
        got = {c["key"] if isinstance(c, dict) else c for c in node.get("referencing_views", [])}
        missing = expected - got
        assert not missing, f"{table}: panel missing pdt-upstream refs {missing} (has {got})"


def test_pdt_consumers_are_direct_not_inherited():
    """Codex round 4 (PR #25): reachability and PDT-consumption are different questions.
    An explore targeting a CHILD view keeps the parent ALIVE (ancestry map) but does NOT
    consume the parent's own PDT materialization (direct map). Pin both maps' answers for
    the fixture chain (test_model.customer -> customer_extended extends base_customer)."""
    from strata_lookml.l1.enrich import direct_view_consumers, view_consumer_map

    graph = build_graph(FIXTURES, FIXTURES / "usage_facts.json")
    ancestry = view_consumer_map(graph)
    direct = direct_view_consumers(graph)

    # Ancestry: the parent inherits the child's consumer (reachability).
    assert "test_model.customer" in ancestry.get("base_customer", [])
    # Direct: the parent has NO direct consumer — its own materialization would be unused.
    assert "test_model.customer" not in direct.get("base_customer", [])
    # The child is a direct consumer target in both maps.
    assert "test_model.customer" in direct.get("customer_extended", [])


def test_evidence_facts_aggregates_content_refs_and_schema_columns():
    """L1 owns aggregation (per outputs/AGENTS.md: outputs serialize, they do not derive).
    `evidence_facts()` computes content-reference counts per explore and per-table column
    facts; renderers only reshape what this function returns (Codex PR #28)."""
    from strata_lookml.l1.enrich import evidence_facts

    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    facts = evidence_facts(graph)

    # A count of 0 means no dict entry at all — the aggregation only records keys it
    # actually saw a content reference for (matches the dashboard's prior `.get(key, 0)`
    # lookup convention, now moved here verbatim).
    assert facts["content_reference_counts"].get("em_legacy_v2.dead_finance_v2", 0) == 0

    live_key = next(
        ref["model"] + "." + ref["explore"] for ref in graph.metadata["l1"]["content_references"]
    )
    assert facts["content_reference_counts"][live_key] >= 1

    table = "acme-analytics.silver.int_attributed_purchases"
    schema_fact = facts["schema_table_facts"][table]
    raw_columns = graph.metadata["l1"]["schema_tables"][table]["columns"]
    assert schema_fact["columns"] == raw_columns
    assert schema_fact["column_count"] == len(raw_columns)


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
        assert d["color"] == NODE_PALETTE["zombie"]
        assert d["estimated_cost_usd"] > 0
        assert d["build_count"] > 0
        assert d["bytes_processed"] > 0
        assert d["used_by_explores"], f"{view}: zombie PDT must list its consumers"
        assert all(c["dead"] for c in d["used_by_explores"])

    # Negative control: a real 'used' PDT must not be flagged zombie/unused, and its
    # consumers must not be mismarked dead.
    live = by_id["pdt:pdt_regional_kpi"]
    assert live["status"] == "used"
    assert live["color"] == NODE_PALETTE["pdt_used"]
    assert live["used_by_explores"]
    assert not any(c["dead"] for c in live["used_by_explores"])


def test_graph_node_detail_status_vocabulary_per_kind():
    """Status vocabulary (dashboard PR #23) — PDT/explore/view nodes carry the honest
    three-way zombie vocabulary instead of a flattened DEAD/ORPHAN flag, with colors
    matching the legend."""
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
    assert zombie_view["color"] == NODE_PALETTE["zombie"]
    assert zombie_view["referencing_explores"], (
        "zombie view must be referenced, not structurally orphaned"
    )
    assert all(c["dead"] for c in zombie_view["referencing_explores"])

    active_view = by_id["view:fct_cart_abandonment"]
    assert active_view["status"] == "active"
    assert active_view["color"] == NODE_PALETTE["view_active"]

    # True orphan (no explore reference at all) is a distinct third state — pull from
    # the smaller FIXTURES set, which has a genuine orphan.
    fixtures_graph = build_graph(FIXTURES, FIXTURES / "usage_facts.json")
    fixtures_data = _build_graph_data(fixtures_graph)
    fixtures_by_id = {n["data"]["id"]: n["data"] for n in fixtures_data["nodes"]}
    orphan_view = fixtures_by_id["view:orphan_view"]
    assert orphan_view["status"] == "orphaned"
    assert orphan_view["color"] == NODE_PALETTE["view_orphan"]
    assert orphan_view["referencing_explores"] == []


def test_graph_node_pdt_dependencies_and_table_references():
    """Explore -> PDT dependency and physical-table -> referencing-view data (dashboard
    PR #23), derived from the graph edges rather than invented."""
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
    whose SQL references the drifted column). Pin that assumption: it's why reports
    surface the Field column instead of collapsing genuinely distinct issues under a
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
    assert any(r.get("field") == "legacy_order_detail.total_unit_cost" for r in drift)


def test_l1_facts_covers_explores_without_usage_rows():
    """Codex PR #28 r5 — live System Activity emits NO row for a never-queried explore,
    so a usage-keyed comprehension drops exactly the explores whose dead verdicts most
    need evidence. Every explore node must get a usage entry; row absence is itself the
    zero-usage fact and is flagged so the sentence states it rather than implying a
    serialized row existed."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)

    # Simulate the live-path gap: strip one dead explore's usage row from L1 entirely.
    removed = "em_legacy_v2.dead_finance_v2"
    del graph.metadata["l1"]["explore_usage"][removed]

    # The backfill is an L1 derivation (r7): pin it at the seam, not just the reshape.
    from strata_lookml.l1.enrich import evidence_facts

    l1_entry = evidence_facts(graph)["explore_usage_evidence"][removed]
    assert l1_entry["no_usage_row"] is True

    assert l1_entry["query_count"] == 0
    assert l1_entry["content_reference_count"] == 0

    # Explores WITH rows are untouched by the backfill (no flag, real counts kept).
    usage = evidence_facts(graph)["explore_usage_evidence"]
    with_row = next(k for k in usage if not usage[k].get("no_usage_row"))
    assert "no_usage_row" not in usage[with_row]


def test_strata_gate_script_and_output_cli(tmp_path):
    gate = subprocess.run(
        [
            sys.executable,
            "-m",
            "strata_lookml.cli.main",
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
            "strata_lookml.cli.main",
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


def test_attention_flag_marks_exactly_the_problem_nodes():
    """The graph's "Needs attention" filter and the empty-panel start-here list read the
    Python-side `attention` flag; pin it against both fixture zombies and live negatives."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    by_id = {
        n["data"]["id"]: n["data"]
        for n in _build_graph_data(build_graph(ENTERPRISE, USAGE, SCHEMA))["nodes"]
    }
    for flagged in (
        "explore:em_legacy_v2:dead_finance_v2",
        "view:legacy_order_detail",
        "pdt:pdt_attribution_full_funnel",
    ):
        assert by_id[flagged]["attention"] is True, flagged
    for clean in (
        "explore:em_finance_base:revenue_trends",
        "view:fct_cart_abandonment",
        "pdt:pdt_regional_kpi",
    ):
        assert by_id[clean]["attention"] is False, clean


def test_analysis_coverage_reads_each_enrichment_marker():
    """`analysis_coverage` is the single answer to "did this check run?". It must follow
    which enrichment actually ran, not whether finding lists happen to be empty."""
    from strata_lookml.l1.enrich import analysis_coverage

    gcs = ROOT / "tests" / "lookml" / "gcs_analytics"
    usage = ROOT / "tests" / "fixtures" / "gcs_usage_facts.json"
    schema = ROOT / "tests" / "fixtures" / "gcs_schema_facts.json"
    assert analysis_coverage(build_graph(gcs)) == {
        "usage": False,
        "schema": False,
        "content": False,
    }
    assert analysis_coverage(build_graph(gcs, usage)) == {
        "usage": True,
        "schema": False,
        "content": True,
    }
    assert analysis_coverage(build_graph(gcs, None, schema)) == {
        "usage": False,
        "schema": True,
        "content": False,
    }
    assert analysis_coverage(build_graph(gcs, usage, schema)) == {
        "usage": True,
        "schema": True,
        "content": True,
    }


def test_active_explores_share_the_dead_code_population():
    """Codex PR #65: `explore_count` counts usage rows, but `_dead_code()` checks every
    resolved explore, so "explore_count - dead explores" undercounts and goes negative when
    unqueried explores have no usage row. L1 now serializes one population (all resolved
    explores) and the active count over it; the KPI shows that value, never JS arithmetic."""
    from strata_lookml.ir.resolver import build_resolved_graph
    from strata_lookml.mcp.tools import strata_usage_summary

    gcs = ROOT / "tests" / "lookml" / "gcs_analytics"
    usage = ROOT / "tests" / "fixtures" / "gcs_usage_facts.json"
    summary = strata_usage_summary(build_graph(gcs, usage))
    assert (summary["ir_explore_count"], summary["dead_explore_count"]) == (7, 2)
    assert summary["active_explore_count"] == 5
    assert summary["dead_view_count"] == 4

    # Usage checks ran but no explore has a usage row or content reference: every explore is
    # dead, explore_count is 0, and the old subtraction gave -7.
    unqueried = enrich_graph(build_resolved_graph(gcs), [], [], [])
    s = strata_usage_summary(unqueried)
    assert s["explore_count"] == 0
    assert s["dead_explore_count"] == s["ir_explore_count"] == 7
    assert s["active_explore_count"] == 0

    # No usage checks: there is no verdict to subtract, so no active count at all.
    assert strata_usage_summary(build_graph(gcs))["active_explore_count"] is None


def test_explores_are_unknown_not_active_when_usage_facts_not_loaded():
    """N7: dead status needs usage evidence, so with none loaded every explore used to render
    green "active". Without usage they carry the neutral "unknown" status/colour (from
    COVERAGE, serialized — not inferred in JS); with usage loaded the active/dead colours
    are unchanged."""
    gcs = ROOT / "tests" / "lookml" / "gcs_analytics"
    usage = ROOT / "tests" / "fixtures" / "gcs_usage_facts.json"

    def page(graph):
        return [
            n["data"] for n in _build_graph_data(graph)["nodes"] if n["data"]["kind"] == "explore"
        ]

    explores = page(build_graph(gcs))
    assert explores
    assert {e["status"] for e in explores} == {"unknown"}
    assert {e["color"] for e in explores} == {NODE_PALETTE["explore_unknown"]}
    assert NODE_PALETTE["explore_unknown"] not in (
        NODE_PALETTE["explore_active"],
        NODE_PALETTE["explore_dead"],
    )

    explores = page(build_graph(gcs, usage))
    assert {e["status"] for e in explores} == {"active", "dead"}
    assert {e["color"] for e in explores} == {
        NODE_PALETTE["explore_active"],
        NODE_PALETTE["explore_dead"],
    }
