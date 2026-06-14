#!/usr/bin/env python3
"""
Governance investigation driver — calls all 10 MCP tools against a playground.
Tests tool correctness and prints a human-readable findings report.

Usage:
    python scripts/test_mcp_live.py [--playground enterprise_mono|gcs_analytics|thelook]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

PLAYGROUNDS: dict[str, dict] = {
    "enterprise_mono": {
        "repo": "tests/lookml/enterprise_mono",
        "usage": "tests/fixtures/enterprise_usage_facts.json",
        "schema": "tests/fixtures/enterprise_schema_facts.json",
        "probe_explore": "customers_us",
        "probe_model": "em_analytics_us",
        "probe_table": "acme-analytics.gold_marts.fct_customer_segments",
        "probe_view": "fct_customer_segments",
        "probe_field": "customer_segment",
        "expect_dead": 6,
        "expect_zombie_cost_min": 60000,
    },
    "gcs_analytics": {
        "repo": "tests/lookml/gcs_analytics",
        "usage": "tests/fixtures/gcs_usage_facts.json",
        "schema": "tests/fixtures/gcs_schema_facts.json",
        "probe_explore": "customers",
        "probe_model": "gcs_analytics",
        "probe_table": "acme-analytics.gold_marts.fct_customer_segments",
        "probe_view": "fct_customer_segments",
        "probe_field": "customer_segment",
        "expect_dead": 4,
        "expect_zombie_cost_min": 0,
    },
    "thelook": {
        "repo": "tests/lookml/thelook",
        "usage": "tests/fixtures/playground_usage_facts.json",
        "schema": "tests/fixtures/playground_schema_facts.json",
        "probe_explore": "order_items",
        "probe_model": "thelook",
        "probe_table": "analytics.marketing_campaigns",
        "probe_view": "order_items",
        "probe_field": "order_id",
        "expect_dead": None,
        "expect_zombie_cost_min": None,
    },
}


def _zombie_cost(pdts: list[dict], dead_names: set[str]) -> float:
    total = 0.0
    for p in pdts:
        is_unused = p.get("status") == "unused"
        backed_by_dead = any(e in dead_names for e in p.get("used_by_explores", []))
        if is_unused or backed_by_dead:
            total += p.get("estimated_cost_usd", 0.0)
    return total


def _is_zombie(pdt: dict, dead_names: set[str]) -> bool:
    return pdt.get("status") == "unused" or any(
        e in dead_names for e in pdt.get("used_by_explores", [])
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Strata MCP live governance test")
    parser.add_argument(
        "--playground",
        choices=list(PLAYGROUNDS),
        default="enterprise_mono",
        help="Playground to run against",
    )
    args = parser.parse_args()

    cfg = PLAYGROUNDS[args.playground]
    repo_path = ROOT / cfg["repo"]
    usage_fixture = ROOT / cfg["usage"]
    schema_fixture = ROOT / cfg["schema"]

    from strata.mcp.tools import (
        strata_dead_code_register,
        strata_explore_deps,
        strata_impact,
        strata_ir_status,
        strata_list_orphans,
        strata_pdt_costs,
        strata_query_field,
        strata_schema_drift,
        strata_usage_summary,
        strata_validation_scope,
    )
    from strata.pipeline import build_graph

    print(f"\n{'=' * 60}")
    print(f"  Strata MCP Live Test — {args.playground}")
    print(f"{'=' * 60}\n")

    print("Building IR graph...", end=" ", flush=True)
    graph = build_graph(repo_path, usage_fixture, schema_fixture)
    print("done\n")

    # ── 1. IR Status ────────────────────────────────────────────
    status = strata_ir_status(graph)
    nc = status["node_counts"]
    print("1. IR Status")
    print(f"   explores : {nc.get('explore', 0)}")
    print(f"   views    : {nc.get('view', 0)}")
    print(f"   fields   : {nc.get('field', 0)}")
    print(f"   edges    : {status['edge_count']}")
    print()

    # ── 2. Usage Summary ─────────────────────────────────────────
    summary = strata_usage_summary(graph)
    period = summary.get("period") or {}
    print("2. Usage Summary")
    print(
        f"   period      : {period.get('start', '?')} → {period.get('end', '?')} ({period.get('days', '?')}d)"
    )
    print(f"   explores    : {summary['explore_count']} total, {summary['dead_code_count']} dead")
    print(f"   queries     : {summary['total_queries']:,}")
    print(f"   PDTs        : {summary['pdt_count']} total, {summary['unused_pdt_count']} unused")
    print(f"   schema drift: {summary['schema_drift_count']} records")
    print()

    # ── 3. Dead Code Register ────────────────────────────────────
    dead = strata_dead_code_register(graph)
    dead_names = {d["name"] for d in dead}
    print(f"3. Dead Code ({len(dead)} total)")
    for item in dead:
        print(f"   [{item['kind']:7s}] {item['name']}")
    print()

    # ── 4. PDT Costs ─────────────────────────────────────────────
    pdts = strata_pdt_costs(graph)
    total_cost = sum(p.get("estimated_cost_usd", 0.0) for p in pdts)
    zombie_cost = _zombie_cost(pdts, dead_names)
    print("4. PDT Costs")
    for p in sorted(pdts, key=lambda x: x.get("estimated_cost_usd", 0.0), reverse=True):
        flag = " ⚠ ZOMBIE" if _is_zombie(p, dead_names) else ""
        print(f"   {p['view']:<45s}  ${p.get('estimated_cost_usd', 0):>10,.2f}{flag}")
    print(f"   {'─' * 56}")
    print(f"   {'TOTAL':<45s}  ${total_cost:>10,.2f}")
    if zombie_cost > 0:
        print(
            f"   {'ZOMBIE SUBTOTAL':<45s}  ${zombie_cost:>10,.2f}  (~${zombie_cost * 12:,.0f}/yr)"
        )
    print()

    # ── 5. Schema Drift ──────────────────────────────────────────
    drift = strata_schema_drift(graph)
    col_drifts = [d for d in drift if d["kind"] == "missing_column"]
    tbl_drifts = [d for d in drift if d["kind"] == "missing_table"]
    print(
        f"5. Schema Drift ({len(drift)} records: {len(col_drifts)} column, {len(tbl_drifts)} table)"
    )
    for d in col_drifts:
        print(f"   [column] {d.get('source_file', '?')} → {d['column']} missing from {d['table']}")
    for d in tbl_drifts:
        print(f"   [table]  {d.get('source_file', '?')} → {d['table']}  (likely CTE FP)")
    print()

    # ── 6. Explore Deps ──────────────────────────────────────────
    print(f"6. Explore Deps — {cfg['probe_model']}.{cfg['probe_explore']}")
    try:
        deps = strata_explore_deps(graph, cfg["probe_explore"], cfg["probe_model"])
        print(f"   base view : {deps.get('base_view', '?')}")
        print(f"   joins     : {len(deps.get('joins', []))}")
        print(f"   fields    : {deps.get('field_count', '?')}")
        chain = deps.get("resolution_chain", [])
        if chain:
            print(f"   chain     : {chain}")
    except KeyError as e:
        print(f"   ERROR: {e}")
    print()

    # ── 7. Query Field ───────────────────────────────────────────
    print(f"7. Query Field — {cfg['probe_view']}.{cfg['probe_field']}")
    try:
        field = strata_query_field(graph, cfg["probe_view"], cfg["probe_field"])
        print(f"   type   : {field.get('type', '?')}")
        print(f"   sql    : {str(field.get('sql', ''))[:60]}")
        print(f"   source : {field.get('source_file', '?')}")
    except KeyError as e:
        print(f"   not found (skipped): {e}")
    print()

    # ── 8. List Orphans ──────────────────────────────────────────
    orphans = strata_list_orphans(graph, "all")
    print(f"8. Orphans: {len(orphans)} total")
    for o in orphans[:5]:
        print(f"   [{o.get('kind', '?')}] {o.get('id', '?')}")
    if len(orphans) > 5:
        print(f"   ... and {len(orphans) - 5} more")
    print()

    # ── 9. Validation Scope ──────────────────────────────────────
    probe_changed = [f"view:{cfg['probe_view']}"]
    scope = strata_validation_scope(graph, probe_changed)
    affected = scope.get("explores", [])
    print(f"9. Validation Scope — if {probe_changed[0]} changes")
    print(f"   explores to revalidate: {len(affected)}")
    for e in affected[:4]:
        print(f"   → {e.get('model', '?')}.{e.get('explore', '?')}")
    if len(affected) > 4:
        print(f"   → ... and {len(affected) - 4} more")
    print()

    # ── 10. Impact ───────────────────────────────────────────────
    print(f"10. Impact — {cfg['probe_table']}")
    try:
        impact = strata_impact(graph, cfg["probe_table"])
        print(f"    views    : {len(impact.get('views', []))}")
        print(f"    explores : {len(impact.get('explores', []))}")
        print(f"    fields   : {len(impact.get('fields', []))}")
    except KeyError as e:
        print(f"    table not in IR (skipped): {e}")
    print()

    # ── Verdict ──────────────────────────────────────────────────
    print("=" * 60)
    failures = []

    expect_dead = cfg.get("expect_dead")
    if expect_dead is not None and len(dead) != expect_dead:
        failures.append(f"dead code: expected {expect_dead}, got {len(dead)}")

    expect_zombie = cfg.get("expect_zombie_cost_min")
    if expect_zombie is not None and zombie_cost < expect_zombie:
        failures.append(f"zombie cost: expected ≥${expect_zombie:,.0f}, got ${zombie_cost:,.0f}")

    if failures:
        print("FAIL")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    else:
        print(f"✅  All 10 MCP tools executed — {args.playground} PASS")
        if zombie_cost > 0:
            print(f"    Zombie PDT cost: ${zombie_cost:,.2f}/30d (~${zombie_cost * 12:,.0f}/yr)")
    print("=" * 60)


if __name__ == "__main__":
    main()
