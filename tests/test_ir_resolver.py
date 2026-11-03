import subprocess
import sys
from pathlib import Path

from strata.ir.builder import build_raw_graph
from strata.ir.parser import parse_repo
from strata.ir.resolver import _sql_upstreams, build_resolved_graph, resolve_graph
from strata.ir.store import load_ir, save_ir

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def test_three_level_chain():
    graph = build_resolved_graph(FIXTURES)

    fields = {
        node.attrs["field_name"]: node
        for node in graph.nodes_by_kind("field")
        if node.attrs.get("view") == "chain_final"
    }
    assert set(fields) == {"id", "base_only", "middle_only", "final_only", "final_count"}
    assert fields["base_only"].attrs["sql"] == "UPPER(${TABLE}.base_only)"
    assert fields["final_only"].attrs["resolution_chain"] == [
        "chain_base",
        "chain_middle",
        "chain_final",
    ]


def test_orphan_detection():
    graph = build_resolved_graph(FIXTURES)

    orphans = graph.metadata["orphans"]
    assert {orphan["name"] for orphan in orphans} == {"orphan_view", "pdt_orders"}


def test_refinement():
    graph = build_resolved_graph(FIXTURES)
    explore = graph.get_node("explore:refined_explore:refined_customer")

    assert explore is not None
    assert explore.attrs["resolution_chain"] == ["refined_customer", "+refined_customer"]
    joins = {join["name"]: join for join in explore.attrs["joins"]}
    assert set(joins) == {"simple", "chain_final"}
    assert explore.attrs["body"]["label"] == "Refined Customer"


def test_cycle_detection_reports_without_crashing(tmp_path):
    (tmp_path / "cycle.view.lkml").write_text(
        """
view: cycle_a {
  extends: [cycle_b]
  dimension: id { sql: ${TABLE}.id ;; }
}

view: cycle_b {
  extends: [cycle_a]
  dimension: id { sql: ${TABLE}.id ;; }
}
""",
        encoding="utf-8",
    )

    graph = resolve_graph(build_raw_graph(parse_repo(tmp_path), tmp_path))

    assert any(error["type"] == "extends_cycle" for error in graph.metadata["resolution_errors"])


def test_store_round_trip(tmp_path):
    graph = build_resolved_graph(FIXTURES)
    cache = tmp_path / "ir.db"

    save_ir(graph, cache)
    loaded = load_ir(cache)

    assert loaded.node_counts() == graph.node_counts()
    assert loaded.metadata["orphans"] == graph.metadata["orphans"]


def test_build_ir_cli_writes_cache(tmp_path):
    cache = tmp_path / "fixture_ir.db"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "strata.cli.main",
            "build",
            "--repo",
            str(FIXTURES),
            "--cache",
            str(cache),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert cache.exists()
    assert load_ir(cache).node_counts()["view"] == 9


def test_sql_upstreams_backtick_quoted_bq_tables():
    """Backtick-quoted BigQuery table names (project-id.dataset.table) must be
    detected as upstreams — the unquoted-identifier regex misses them because
    hyphens in project names are not word characters."""
    sql = """
        SELECT customer_id, COUNT(*) AS cnt
        FROM `acme-analytics.silver.int_orders` o
        JOIN `acme-analytics.gold.fct_revenue` r ON o.customer_id = r.customer_id
        GROUP BY 1
    """
    result = _sql_upstreams(sql)
    assert "acme-analytics.silver.int_orders" in result
    assert "acme-analytics.gold.fct_revenue" in result


def test_sql_upstreams_unquoted_tables_unaffected():
    """Existing behaviour for unquoted identifiers must not regress."""
    sql = "SELECT customer_id FROM analytics.orders GROUP BY customer_id"
    assert _sql_upstreams(sql) == ["analytics.orders"]


def test_sql_upstreams_cte_not_treated_as_upstream():
    """CTE names must not appear as physical upstreams."""
    sql = """
        WITH ranked AS (SELECT id FROM analytics.events)
        SELECT * FROM ranked
    """
    result = _sql_upstreams(sql)
    assert "ranked" not in result
    assert "analytics.events" in result
