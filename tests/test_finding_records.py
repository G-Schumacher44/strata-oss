"""`finding_records`: the one finding source the gate and the baseline project from."""

import json
from pathlib import Path

import pytest

from strata_lookml.gate import baseline_document, evaluate_gate, finding_records, write_baseline
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
