"""Workbench S4c: `strata findings` / `ack` / `unack` over the triage core."""

import dataclasses
import hashlib
import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from strata_lookml.cli.main import strata_cli
from strata_lookml.gate import write_baseline
from strata_lookml.pipeline import build_graph
from strata_lookml.triage import TriageStore, triage_rows

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).parent / "lookml" / "enterprise_mono"
USAGE = FIXTURES / "enterprise_usage_facts.json"
SCHEMA = FIXTURES / "enterprise_schema_facts.json"
ARGS = ["--repo", str(REPO), "--usage-fixture", str(USAGE), "--schema-fixture", str(SCHEMA)]
# vim's default errorformat entry for a file:line:message list
QUICKFIX = re.compile(r"^(?P<file>[^:]+):(?P<line>\d+):(?P<msg>.*)$")
ID_OF = re.compile(r".* \((.*)\)$")


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for var in ("STRATA_REPO_PATH", "STRATA_USAGE_FIXTURE", "STRATA_SCHEMA_FIXTURE"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(scope="module")
def graph():
    return build_graph(REPO, USAGE, SCHEMA)


def run(*args, input=None):
    return CliRunner().invoke(strata_cli, list(args), input=input)


def findings(*extra):
    result = run("findings", *ARGS, *extra)
    assert result.exit_code == 0, result.output
    return result.stdout


def _tree():
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in REPO.rglob("*") if p.is_file()
    }


def _expected(graph, home_repo=REPO, baseline=None):
    return triage_rows(graph, baseline, TriageStore.open(home_repo, graph))


def test_json_matches_triage_rows_and_defaults_to_new(graph):
    rows = json.loads(findings("--format", "json"))
    expected = [dataclasses.asdict(r) for r in _expected(graph) if r.status == "new"]
    assert rows == expected and rows
    everything = json.loads(findings("--format", "json", "--status", "all"))
    assert everything == [dataclasses.asdict(r) for r in _expected(graph)]


def test_category_and_status_filters(graph):
    rows = json.loads(findings("--format", "json", "--category", "drift"))
    assert rows and {r["category"] for r in rows} == {"drift"}
    assert json.loads(findings("--format", "json", "--status", "fixed")) == []


def test_lines_parse_as_vim_quickfix_and_carry_the_id(graph):
    out = findings("--format", "lines").splitlines()
    expected = [r for r in _expected(graph) if r.status == "new"]
    assert len(out) == len(expected)
    for text, row in zip(out, expected, strict=True):
        match = QUICKFIX.match(text)
        assert match, text
        assert match["file"] == row.source_file
        assert int(match["line"]) == row.source_line
        assert f"[{row.category}]" in match["msg"]
        assert ID_OF.match(text)[1] == row.id


def test_rows_without_a_file_print_a_dash_prefix(tmp_path):
    baseline = tmp_path / "base.json"
    baseline.write_text(
        json.dumps({"version": 1, "findings": {"dead-code": ["dead:view:long_gone"]}})
    )
    result = run("findings", *ARGS, "--baseline", str(baseline), "--status", "baselined")
    assert result.exit_code == 0, result.output
    # the baselined-but-gone id is a fixed row with no location
    lines = findings("--baseline", str(baseline), "--status", "fixed", "--format", "lines")
    assert lines.splitlines() == [
        "-:0: [dead-code] dead:view:long_gone — no longer found (dead:view:long_gone)"
    ]
    assert QUICKFIX.match(lines.splitlines()[0])


def test_table_has_header_and_one_row_per_finding(graph):
    out = findings().splitlines()
    assert out[0].split()[:4] == ["STATUS", "CATEGORY", "LOCATION", "FINDING"]
    assert len(out) - 1 == len([r for r in _expected(graph) if r.status == "new"])


def test_ack_then_findings_and_unack():
    first = json.loads(findings("--format", "json"))[0]["id"]
    result = run("ack", *ARGS, "--note", "kept on purpose", first)
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == f"acknowledged: {first}"
    assert first not in findings("--format", "lines")
    rows = json.loads(findings("--format", "json", "--status", "acknowledged"))
    assert [(r["id"], r["note"]) for r in rows] == [(first, "kept on purpose")]

    again = run("ack", *ARGS, first)
    assert again.stdout.strip() == f"already acknowledged: {first}"

    result = run("unack", *ARGS, first)
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == f"unacknowledged: {first}"
    assert any(r["id"] == first for r in json.loads(findings("--format", "json")))


def test_ack_reads_ids_from_stdin_via_the_documented_pipeline():
    lines = findings("--format", "lines").splitlines()[:2]
    stdin = "\n".join(ID_OF.match(line)[1] for line in lines) + "\n\n"
    result = run("ack", *ARGS, "-", input=stdin)
    assert result.exit_code == 0, result.output
    acked = json.loads(findings("--format", "json", "--status", "acknowledged"))
    assert [r["id"] for r in acked] == [ID_OF.match(line)[1] for line in lines]


def test_unknown_id_exits_1_and_writes_nothing(tmp_path):
    good = json.loads(findings("--format", "json"))[0]["id"]
    result = run("ack", *ARGS, good, "dead:view:no_such_thing")
    assert result.exit_code == 1
    assert "not a current finding id" in result.stderr
    assert not (tmp_path / "home" / ".strata" / "triage").exists() or not list(
        (tmp_path / "home" / ".strata" / "triage").glob("*.json")
    )
    assert json.loads(findings("--format", "json", "--status", "acknowledged")) == []
    assert run("unack", *ARGS, good).exit_code == 1  # never acknowledged


def test_no_ids_is_a_usage_error():
    assert run("ack", *ARGS, "-", input="\n").exit_code == 2


def test_baselined_wins_over_ack(tmp_path, graph):
    baseline = tmp_path / "base.json"
    write_baseline(graph, baseline)
    target = json.loads(findings("--format", "json"))[0]["id"]
    assert run("ack", *ARGS, target).exit_code == 0
    rows = json.loads(findings("--baseline", str(baseline), "--status", "all", "--format", "json"))
    row = next(r for r in rows if r["id"] == target)
    assert row["status"] == "baselined"
    assert row["acked_at"]  # the ack is kept and shown


def test_ack_leaves_the_repo_tree_untouched():
    before = _tree()
    first = json.loads(findings("--format", "json"))[0]["id"]
    assert run("ack", *ARGS, first).exit_code == 0
    assert run("unack", *ARGS, first).exit_code == 0
    assert _tree() == before


def test_env_vars_replace_the_options(monkeypatch):
    monkeypatch.setenv("STRATA_REPO_PATH", str(REPO))
    monkeypatch.setenv("STRATA_USAGE_FIXTURE", str(USAGE))
    monkeypatch.setenv("STRATA_SCHEMA_FIXTURE", str(SCHEMA))
    result = run("findings", "--format", "json")
    assert result.exit_code == 0 and json.loads(result.stdout)
