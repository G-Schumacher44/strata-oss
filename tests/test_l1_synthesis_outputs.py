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


def test_physical_table_panel_counts_pdt_upstream_references():
    """Codex r5 (PR #25): derived-table SQL references (pdt→upstream) must appear in the
    physical-table panel's referencing list, mirroring strata_impact()'s mapping — the
    panel must never undercount the references a deletion would break."""
    from strata.outputs.dashboard import _build_graph_data

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


def test_evidence_facts_aggregates_content_refs_and_schema_columns():
    """L1 owns aggregation (per outputs/AGENTS.md: outputs serialize, they do not derive).
    `evidence_facts()` computes content-reference counts per explore and per-table column
    facts; `dashboard._build_l1_facts()` only reshapes what this function returns into the
    evidence-id-keyed shape the JS looks up (Codex PR #28)."""
    from strata.l1.enrich import evidence_facts

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


def test_l1_facts_inlines_usage_pdt_build_and_schema_table_facts():
    """Slice 08 — the raw L1 facts (explore_usage, pdt_builds, schema_tables) must reach
    the dashboard data block Python-side, keyed to match the evidence-id suffixes the JS
    looks them up by, so evidence sentences never re-derive a number the L1 layer already
    computed."""
    from strata.outputs.dashboard import _build_l1_facts

    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    facts = _build_l1_facts(graph)

    assert facts["period"] == {"start": "2026-05-07", "end": "2026-06-06", "days": 30}

    dead_finance = facts["usage"]["explore:em_legacy_v2.dead_finance_v2"]
    assert dead_finance["query_count"] == 0
    assert dead_finance["content_reference_count"] == 0

    live_explore_key = next(
        key for key, rec in graph.metadata["l1"]["explore_usage"].items() if rec["query_count"] > 0
    )
    assert facts["usage"][f"explore:{live_explore_key}"]["query_count"] > 0

    zombie_build = facts["pdt_build"]["pdt_attribution_full_funnel"]
    assert zombie_build["build_count"] == 180
    assert zombie_build["estimated_cost_usd"] == 45000.0
    assert zombie_build["bytes_processed"] == 7200000000000000

    schema_table = facts["schema_table"]["acme-analytics.silver.int_attributed_purchases"]
    assert schema_table["column_count"] > 0
    assert schema_table["columns"], "column NAMES must be plumbed, not just a count (Codex PR #28)"
    assert schema_table["column_count"] == len(schema_table["columns"])


def test_l1_facts_covers_explores_without_usage_rows():
    """Codex PR #28 r5 — live System Activity emits NO row for a never-queried explore,
    so a usage-keyed comprehension drops exactly the explores whose dead verdicts most
    need evidence. Every explore node must get a usage entry; row absence is itself the
    zero-usage fact and is flagged so the sentence states it rather than implying a
    serialized row existed."""
    from strata.outputs.dashboard import _build_l1_facts

    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)

    # Simulate the live-path gap: strip one dead explore's usage row from L1 entirely.
    removed = "em_legacy_v2.dead_finance_v2"
    del graph.metadata["l1"]["explore_usage"][removed]

    # The backfill is an L1 derivation (r7): pin it at the seam, not just the reshape.
    from strata.l1.enrich import evidence_facts

    l1_entry = evidence_facts(graph)["explore_usage_evidence"][removed]
    assert l1_entry["no_usage_row"] is True

    facts = _build_l1_facts(graph)
    entry = facts["usage"][f"explore:{removed}"]
    assert entry == l1_entry, "outputs must reshape the L1 record verbatim, not re-derive"
    assert entry["no_usage_row"] is True
    assert entry["query_count"] == 0
    assert entry["content_reference_count"] == 0

    # Explores WITH rows are untouched by the backfill (no flag, real counts kept).
    with_row = next(k for k in facts["usage"] if not facts["usage"][k].get("no_usage_row"))
    assert "no_usage_row" not in facts["usage"][with_row]


def test_embedded_json_cannot_break_out_of_script_block():
    """Codex PR #28 r6 — json.dumps leaves `<` intact, so a data value containing
    `</script>` would terminate the inline script element and hand the rest of the
    payload to the HTML parser as live markup. Every JSON embed goes through
    `_embed_json`, which encodes `<` as `\\u003c` (identical after JS string parsing)."""
    from strata.outputs.dashboard import _embed_json, build_dashboard_html  # noqa: F401

    hostile = {"period": {"start": "</script><b>x</b>"}, "col": "a<b"}
    embedded = _embed_json(hostile)
    assert "</script>" not in embedded
    assert "<" not in embedded
    import json as _json

    assert _json.loads(embedded) == hostile  # pure serialization change

    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    # Poison a value that lands in the L1_FACTS script literal; the generated page must
    # not contain the sequence raw anywhere inside its scripts.
    graph.metadata["l1"]["period"] = {"start": "</script><i>pwn</i>", "end": "x", "days": 30}
    html = build_dashboard_html(build_artifacts(graph), graph)
    import re

    for m in re.finditer(r"<script>([\s\S]*?)</script>", html):
        assert "<i>pwn</i>" not in m.group(1)


def test_evidence_namespaces_all_have_sentence_handling():
    """Hard constraint (slice-08): every evidence-id namespace present in the shipped
    artifacts must resolve to a rendered sentence or a named, deliberate fallback — a
    namespace the dashboard's evidenceSentence() dispatcher doesn't handle silently
    no-ops for the user. Enumerate the REAL enterprise_mono artifacts (not a synthetic
    list) and pin them against dashboard.py's documented namespace set, then confirm the
    generated JS actually carries a case for each one."""
    from strata.outputs.dashboard import KNOWN_EVIDENCE_NAMESPACES, build_dashboard_html

    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    artifacts = build_artifacts(graph)

    found: set[str] = set()

    def walk(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "evidence_ids" and isinstance(value, list):
                    for eid in value:
                        found.add(str(eid).split(":", 1)[0])
                else:
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(artifacts)

    assert found, "fixture must exercise at least one evidence namespace"
    assert found <= KNOWN_EVIDENCE_NAMESPACES, (
        f"artifact evidence ids use namespace(s) {found - KNOWN_EVIDENCE_NAMESPACES} not "
        "declared in dashboard.py's KNOWN_EVIDENCE_NAMESPACES — add a case to "
        "evidenceSentence() and the constant before shipping"
    )

    html = build_dashboard_html(artifacts, graph)
    for namespace in found:
        assert f"case '{namespace}'" in html, (
            f"generated dashboard JS has no evidenceSentence() case for '{namespace}'"
        )


def test_schema_table_sentence_renders_known_column_names():
    """A missing_column finding's evidence chips were unverifiable: the `field:` sentence
    is a declared no-fact fallback and `schema_table:` only reported a column COUNT.
    Preserve the FULL column-name list (no display cap — a truncated list hides exactly
    the fact a reader needs: whether the missing column is among the hidden ones, Codex
    PR #28 round 3) so a reader can see the named column is absent."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    artifacts = build_artifacts(graph)
    html = build_dashboard_html(artifacts, graph)

    assert "fact.columns" in html
    assert "cols.slice(0, 30)" not in html, "the 30-column display cap must be removed"
    assert "cols.join(', ')" in html
    # field: fallback stays the honest, unchanged no-fact message.
    assert "no field-level L1 fact is tracked for" in html


def test_physical_table_evidence_namespace_resolves_present_and_missing():
    """missing_table drift records cite the physical table's OWN graph node id
    (`physical_table:<name>`) as evidence_ids[0] — the Cleanup Roadmap uses that as its
    primary chip, so evidenceSentence() must handle the `physical_table` namespace rather
    than fall through to the generic no-sentence default (Codex PR #28)."""
    graph = build_graph(
        FIXTURES, FIXTURES / "usage_facts.json", FIXTURES / "schema_facts_drift.json"
    )
    artifacts = build_artifacts(graph)
    html = build_dashboard_html(artifacts, graph)

    drift = artifacts["schema_drift"]
    missing_tables = [r for r in drift if r["kind"] == "missing_table"]
    assert missing_tables, "fixture must exercise a missing_table drift record"
    assert missing_tables[0]["evidence_ids"][0].startswith("physical_table:")

    assert "case 'physical_table'" in html
    assert "is not present in the provided schema facts" in html
    assert "scanned ${scanned}" in html


def test_schema_drift_and_roadmap_rows_get_stable_ids_and_copy_links():
    """Slice contract (conductor/slice-08-evidence-trust-core.md lines 22 + 45): ANY
    finding is shareable and EVERY row gets a copy-link affordance — Codex found only Dead
    Code Register and PDT Ledger rows shipped it. Extend the same primaryChipHtml()-based
    pattern to Schema Drift and Cleanup Roadmap rows, reusing each row's own pre-existing
    evidence ids rather than inventing a new id scheme (Codex PR #28)."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    artifacts = build_artifacts(graph)
    html = build_dashboard_html(artifacts, graph)

    drift = artifacts["schema_drift"]
    assert drift, "fixture must exercise schema drift rows"
    assert all(r["id"].startswith("schema:") for r in drift)

    roadmap = artifacts["cleanup_roadmap"]
    assert roadmap, "fixture must exercise roadmap rows"
    assert all(r["evidence_ids"] for r in roadmap)

    # Schema Drift: the DOM row id is the row's own SchemaDriftRecord id (several rows can
    # share one table, so `schema_table:` alone isn't unique enough); the chip itself still
    # resolves via `schema_table:`, one of the row's own pre-existing evidence ids.
    assert "tr.id = r.id;" in html
    assert "primaryChipHtml('schema_table:' + r.table, chipLabel, r.id)" in html

    # Cleanup Roadmap items carry no own artifact id. The chip's evidence id (primaryId)
    # is the row's own evidence_ids[0] verbatim, unchanged; the DOM anchor/copy-link is a
    # SEPARATE 'roadmap:' namespace (can never collide with a ledger/register row's own
    # id), with a ':N' suffix disambiguating multiple actions that share one primaryId.
    assert "const primaryId = r.evidence_ids[0];" in html
    assert "let roadmapId = 'roadmap:' + primaryId;" in html
    assert "li.id = roadmapId;" in html
    assert "primaryChipHtml(primaryId, r.target, roadmapId)" in html
    # The round-3 defer-if-taken rule is dead now that 'roadmap:' ids can never collide.
    assert "if (!document.getElementById(primaryId)) li.id = primaryId;" not in html


def test_roadmap_and_ledger_dom_ids_are_all_unique():
    """Regression for the duplicate-DOM-id bug a live browser pass caught (round 2): every
    row/li in the generated dashboard must have a unique id, or `getElementById` silently
    resolves only the first match and later rows/anchors become unreachable. Cheap
    Python-side check — reproduce the JS id-assignment scheme against the artifact data
    rather than standing up a DOM (Codex PR #28)."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    artifacts = build_artifacts(graph)

    roadmap = artifacts["cleanup_roadmap"]
    assert roadmap, "fixture must exercise roadmap rows"

    seen: dict[str, int] = {}
    dupes: dict[str, int] = {}
    for r in roadmap:
        primary_id = r["evidence_ids"][0]
        roadmap_id = f"roadmap:{primary_id}"
        seen[roadmap_id] = seen.get(roadmap_id, 0) + 1
        if seen[roadmap_id] > 1:
            roadmap_id = f"{roadmap_id}:{seen[roadmap_id]}"
        dupes[roadmap_id] = dupes.get(roadmap_id, 0) + 1

    assert all(count == 1 for count in dupes.values()), (
        f"the roadmap:-prefixed id-collision resolution produced duplicates: {dupes}"
    )

    ledger_ids = {f"pdt:{r['view']}" for r in artifacts["pdt_ledger"]}
    dead_ids = {r["id"] for r in artifacts["dead_code_register"]}
    drift_ids = {r["id"] for r in artifacts["schema_drift"]}
    roadmap_ids = set(dupes.keys())
    assert not roadmap_ids & (ledger_ids | dead_ids | drift_ids), (
        "roadmap: namespace must never collide with a ledger/register/drift row's own id"
    )


def test_evidence_sentence_panel_assigned_via_text_content():
    """Output-encoding hardening: evidence sentences interpolate fixture-supplied fields
    (e.g. period.start/end, source_file); the panel must be assigned via textContent, not
    innerHTML, so markup in fixture data can never render as markup (Codex PR #28)."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    artifacts = build_artifacts(graph)
    html = build_dashboard_html(artifacts, graph)

    assert "panel.textContent = evId + ': ' + evidenceSentence(evId);" in html
    # The sentence-building helpers no longer need to HTML-escape fixture-supplied fields
    # now that nothing assigns their output via innerHTML (evidenceHtml()'s own
    # escapeHtml(evId) call is unrelated — that's a real innerHTML pill label, correctly
    # still escaped).
    assert "escapeHtml(modelDotName)" not in html
    assert "escapeHtml(sourceFile)" not in html
    assert "No graph node found for evidence id '${evId}'." in html


def test_evidence_chips_and_deep_links_present_in_generated_html():
    """Both fixture zombies must be reachable via a literal #dead:explore:.../#pdt:...
    hash target with a copy-link affordance — the deep-link contract slice-08 adds."""
    ENTERPRISE = ROOT / "tests" / "lookml" / "enterprise_mono"
    USAGE = ROOT / "tests" / "fixtures" / "enterprise_usage_facts.json"
    SCHEMA = ROOT / "tests" / "fixtures" / "enterprise_schema_facts.json"
    graph = build_graph(ENTERPRISE, USAGE, SCHEMA)
    artifacts = build_artifacts(graph)
    html = build_dashboard_html(artifacts, graph)

    assert '"dead:explore:em_legacy_v2.dead_finance_v2"' in html
    assert '"pdt:pdt_attribution_full_funnel"' in html
    assert '"pdt:pdt_customer_value_score"' in html
    assert "copy-link-btn" in html
    assert "openHashTarget" in html
    assert "evidence-sentence" in html


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
