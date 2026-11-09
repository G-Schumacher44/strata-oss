"""`finding_records`: the one finding source the gate and the baseline project from."""

import json
from pathlib import Path

import pytest

from strata_lookml.gate import (
    _integrity_failures,
    baseline_document,
    evaluate_gate,
    finding_records,
    write_baseline,
)
from strata_lookml.pipeline import build_graph

FIXTURES = Path(__file__).parent / "fixtures"
LOOKML = Path(__file__).parent / "lookml"
REPOS = {
    "enterprise_mono": ("enterprise_usage_facts.json", "enterprise_schema_facts.json"),
    "gcs_analytics": ("gcs_usage_facts.json", "gcs_schema_facts.json"),
}


def _graph(repo):
    usage, schema = REPOS[repo]
    return build_graph(LOOKML / repo, FIXTURES / usage, FIXTURES / schema)


@pytest.mark.parametrize("repo", REPOS)
def test_every_record_resolves_to_a_subject_with_a_source_line(repo):
    graph = _graph(repo)
    records = finding_records(graph)

    assert {r["category"] for r in records} >= {"dead-code", "drift"}
    for r in records:
        assert graph.get_node(r["subject_id"]) is not None, r["id"]
        assert r["source_file"], r["id"]
        assert isinstance(r["source_line"], int), r["id"]
        assert r["label"] and r["evidence_ids"], r["id"]
        assert ("cost_usd" in r) == r["category"].endswith("-pdt"), r["id"]


def test_pdt_records_cite_their_views_line():
    graph = _graph("enterprise_mono")
    pdts = [r for r in finding_records(graph) if r["category"] == "zombie-pdt"]

    assert pdts
    for r in pdts:
        view = graph.get_node(f"view:{r['id'].removeprefix('pdt:')}")
        assert r["source_line"] == view.attrs["source_line"]
        assert r["cost_usd"] > 0


def test_labels_per_category():
    by_cat: dict[str, list[dict]] = {}
    for r in finding_records(_graph("enterprise_mono")) + finding_records(_graph("gcs_analytics")):
        by_cat.setdefault(r["category"], []).append(r)

    for r in by_cat["dead-code"]:
        assert r["label"] == r["id"].split(":", 2)[2]
    for r in by_cat["zombie-pdt"]:
        assert r["label"] == r["id"].removeprefix("pdt:")
    columns = [r for r in by_cat["drift"] if r["id"].startswith("schema:missing_column:")]
    tables = [r for r in by_cat["drift"] if r["id"].startswith("schema:missing_table:")]
    assert columns and tables
    for r in columns:
        field = r["id"].rsplit(":", 1)[1]
        column = r["id"].split(":")[2].rsplit(".", 1)[1]
        table = r["id"].split(":")[2].rsplit(".", 1)[0].split(".")[-1]
        assert r["label"] == f"{field} ← {table}.{column}"
    for r in tables:
        assert r["label"] == ".".join(r["id"].split(":", 2)[2].split(".")[-2:])
        assert r["label"].count(".") == 1


def test_duplicate_ids_keep_every_record_and_the_baseline_dedupes(tmp_path):
    graph = _graph("enterprise_mono")
    drift = graph.metadata["l1"]["schema_drift"]
    column = next(r for r in drift if r["kind"] == "missing_column")
    drift.append(dict(column, source_file="other.view.lkml"))

    same = [r for r in finding_records(graph) if r["id"] == column["id"]]
    assert len(same) == 2
    ids = baseline_document(graph)["findings"]["drift"]
    assert ids.count(column["id"]) == 1
    target = tmp_path / "b.json"
    assert write_baseline(graph, target) == sum(
        len(v) for v in json.loads(target.read_text())["findings"].values()
    )
    assert evaluate_gate(graph, {"drift"}, {"drift": set(ids)})["passed"]


def test_a_resolution_error_is_an_integrity_record_with_no_guessed_location(tmp_path):
    (tmp_path / "orders.view.lkml").write_text(
        "view: orders {\n  extends: [gone]\n  dimension: id { sql: ${TABLE}.id ;; }\n}\n",
        encoding="utf-8",
    )
    records = finding_records(build_graph(tmp_path))

    assert [(r["category"], r["id"]) for r in records] == [
        ("integrity", "resolution:view:missing_extends_target:gone")
    ]
    record = records[0]
    assert record["label"] == "gone: missing extends target"
    assert record["subject_id"] is None
    assert record["source_file"] is None and record["source_line"] is None
    assert _integrity_failures(build_graph(tmp_path)) == [
        {k: record[k] for k in ("category", "id", "message")}
    ]


def test_an_explore_integrity_failure_cites_its_explore(monkeypatch):
    graph = _graph("gcs_analytics")
    monkeypatch.setattr(
        "strata_lookml.gate.validate_verdict", lambda verdict, evidence: ["bad verdict"]
    )
    records = [r for r in finding_records(graph) if r["category"] == "integrity"]

    assert records
    for r in records:
        node = graph.get_node(r["subject_id"])
        assert node is not None and node.kind == "explore" and r["id"] == node.id
        assert r["source_file"] == node.source_file
        assert r["source_line"] == node.attrs["source_line"]
        assert r["message"] == "bad verdict"


def _missing_table_record(tmp_path, files):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    schema = tmp_path / "schema.json"
    schema.write_text('{"tables": [{"name": "ds.other", "columns": ["id"]}]}', encoding="utf-8")
    graph = build_graph(tmp_path, None, schema)
    records = [r for r in finding_records(graph) if r["id"] == "schema:missing_table:ds.gone"]
    assert len(records) == 1
    return graph, records[0]


_PDT = (
    "view: summary {\n  derived_table: {\n    sql: select id from ds.gone ;;\n  }\n"
    "  dimension: id {\n    sql: ${TABLE}.id ;;\n  }\n}\n"
)
_DIRECT = "view: direct {\n  sql_table_name: ds.gone ;;\n}\n"


def test_a_table_read_only_by_pdt_sql_cites_the_pdt_view(tmp_path):
    graph, record = _missing_table_record(tmp_path, {"a_summary.view.lkml": _PDT})

    view = graph.get_node("view:summary")
    assert (record["source_file"], record["source_line"]) == (view.source_file, 1)


def test_a_table_read_by_a_pdt_and_a_view_cites_one_nodes_file_and_line(tmp_path):
    # The PDT file sorts first, so it created the table node; the direct view is cited instead
    # only if its (file, line) wins. Whichever wins, file and line must be the same node's.
    (first, second) = (tmp_path / "one", tmp_path / "two")
    first.mkdir(), second.mkdir()
    graph, record = _missing_table_record(
        first, {"b_summary.view.lkml": _PDT, "a_direct.view.lkml": "\n\n\n" + _DIRECT}
    )

    assert (record["source_file"], record["source_line"]) == ("a_direct.view.lkml", 4)
    graph, record = _missing_table_record(
        second, {"a_summary.view.lkml": _PDT, "b_direct.view.lkml": _DIRECT}
    )
    assert (record["source_file"], record["source_line"]) == ("a_summary.view.lkml", 1)
