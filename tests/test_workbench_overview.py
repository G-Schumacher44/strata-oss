"""Workbench Overview (S7): numbers equal the tools', skipped checks say "not run", SVG is numeric."""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

import pytest

from strata_lookml.cli.dashboard import allowed_hosts
from strata_lookml.mcp.tools import strata_pdt_costs, strata_usage_summary
from strata_lookml.workbench import overview as ov
from strata_lookml.workbench.app import App
from strata_lookml.workbench.charts import bar
from strata_lookml.workbench.index import Staleness, Workbench, index_graph, load_graph

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "lookml" / "gcs_analytics"
FIX = ROOT / "fixtures"
USAGE = FIX / "gcs_usage_facts.json"
SCHEMA = FIX / "gcs_schema_facts.json"
PORT = 18766
HOST = f"127.0.0.1:{PORT}"
HOSTILE = "<img src=x onerror=alert(1)>"


@pytest.fixture(autouse=True)
def _home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("STRATA_CACHE_PATH", raising=False)


def _wb(repo: Path, usage: Path | None, schema: Path | None) -> Workbench:
    graph, inputs = load_graph(repo, str(usage) if usage else None, str(schema) if schema else None)
    return index_graph(
        graph,
        repo=repo,
        usage_fixture=str(usage) if usage else None,
        schema_fixture=str(schema) if schema else None,
        inputs=inputs,
    )


def _page(wb: Workbench) -> str:
    app = App(wb, allowed_hosts(PORT), "tok", Staleness(wb.inputs, wb.fingerprint))
    r = app.respond("GET", "/overview", HOST)
    assert r.status == 200
    return r.body.decode()


def _text(html: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))


@pytest.fixture(scope="module")
def full() -> tuple[Workbench, str]:
    wb = _wb(REPO, USAGE, SCHEMA)
    return wb, _page(wb)


def test_numbers_equal_the_tools(full: tuple[Workbench, str]) -> None:
    wb, html = full
    text = _text(html)
    usage = strata_usage_summary(wb.graph)
    assert (
        f"ran {usage['total_queries']:,} queries across {usage['ir_explore_count']:,} explores"
        in text
    )
    assert (
        f"{usage['active_explore_count']:,} are active and {usage['dead_explore_count']:,} are dead"
        in text
    )
    zw = [r for r in strata_pdt_costs(wb.graph) if r["status"] in ("zombie", "unused")]
    total = sum(r["estimated_cost_usd"] for r in strata_pdt_costs(wb.graph))
    assert ov.usd(sum(r["estimated_cost_usd"] for r in zw)) in text
    assert f"of the {ov.usd(total)} estimated rebuild cost over 30 days" in text
    for r in strata_pdt_costs(wb.graph):
        assert r["view"] in text
        assert ov.usd(r["estimated_cost_usd"]) in text


def test_not_run_without_facts_never_zero() -> None:
    text = _text(_page(_wb(REPO, None, None)))
    assert text.count("Not run") >= 3 and "not run" in text
    assert "Usage checks: not run, load usage facts" in text
    assert "objects, findings not run" in text and "0 findings" not in text
    for forbidden in ("0 dead", "are dead", "$0", "zombie or unused", "across 0"):
        assert forbidden not in text
    assert "<svg" not in _page(_wb(REPO, None, None)).split("<article")[1]


def test_mutation_flipping_coverage_changes_the_sentence() -> None:
    usage_only = _text(_page(_wb(REPO, USAGE, None)))
    schema_only = _text(_page(_wb(REPO, None, SCHEMA)))
    assert "Not run — load schema facts" in usage_only and "are dead" in usage_only
    assert "Not run — load usage facts to see query volume" in schema_only
    assert "Missing from the warehouse" in schema_only and "are dead" not in schema_only


def test_window_label_is_honest() -> None:
    assert ov.window_label({"days": 30}) == "30 days"
    assert ov.window_label({"days": 14}) == "14 days"
    assert ov.window_label({"start": "a"}) is None
    assert ov.window_label(None) is None


def test_window_other_than_30_days(tmp_path: Path) -> None:
    facts = json.loads(USAGE.read_text())
    facts["period"] = {"start": "2026-05-24", "end": "2026-06-06", "days": 14}
    path = tmp_path / "usage14.json"
    path.write_text(json.dumps(facts))
    text = _text(_page(_wb(REPO, path, SCHEMA)))
    assert "over 14 days" in text and "30" not in re.findall(r"/ \d+ days", text)
    assert "/mo" not in text and "/ 14 days" in text
    facts.pop("period")
    path.write_text(json.dumps(facts))
    text = _text(_page(_wb(REPO, path, SCHEMA)))
    assert "length not recorded" in text and "30 days" not in text


def test_bar_emits_only_numeric_attributes() -> None:
    svg = bar(3, 12, width=100, height=6)
    for name, value in re.findall(r'([\w-]+)="([^"]*)"', svg):
        if name in {"class", "role", "aria-hidden", "focusable", "viewBox"}:
            continue
        assert re.fullmatch(r"\d+", value), (name, value)
    assert 'width="25"' in svg and "<text" not in svg
    assert 'class="fill"' not in bar(0, 5) and 'class="fill"' not in bar(5, 0)
    assert 'width="120"' in bar(99, 5)  # clamped to the track
    assert 'class="fill"' in bar(1, 10_000)  # a small share stays visible
    for bad in (HOSTILE, None, True, float("nan"), float("inf")):
        with pytest.raises((TypeError, ValueError)):
            bar(bad, 5)  # type: ignore[arg-type]
        with pytest.raises((TypeError, ValueError)):
            bar(5, bad)  # type: ignore[arg-type]


def test_hostile_names_are_escaped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "m.model.lkml").write_text(
        f'connection: "c"\ninclude: "*.view.lkml"\nexplore: "{HOSTILE}" {{ from: v }}\n'
        "explore: live { from: v }\n",
        encoding="utf-8",
    )
    (repo / "v.view.lkml").write_text(
        "view: v { sql_table_name: `p.d.t<b>` ;; dimension: c { sql: ${TABLE}.nope ;; } }\n"
        'view: "p<i>" { derived_table: { sql: select 1 ;; datagroup_trigger: g } }\n',
        encoding="utf-8",
    )
    usage = tmp_path / "u.json"
    usage.write_text(
        json.dumps(
            {
                "period": {"days": 30},
                "explore_usage": [{"model": "m", "explore": "live", "query_count": 5}],
                "content_references": [],
                "pdt_builds": [
                    {
                        "view": "p<i>",
                        "build_count": 2,
                        "last_built_at": "2026-06-01T00:00:00Z",
                        "bytes_processed": 1,
                        "estimated_cost_usd": 7.0,
                    }
                ],
            }
        )
    )
    schema = tmp_path / "s.json"
    schema.write_text(json.dumps({"tables": [{"name": "p.d.t<b>", "columns": ["id"]}]}))
    html = _page(_wb(repo, usage, schema))
    assert (
        HOSTILE not in html
        and "<img" not in html
        and "<b>" not in html
        and "<i>" not in html.replace("<i ", "")
    )
    assert "&lt;" in html
    assert "p.d.t&lt;b&gt;" in html


def test_no_chartjs_in_workbench_templates() -> None:
    root = Path(ov.__file__).parent
    for path in (*root.glob("templates/*"), *root.glob("*.py")):
        text = path.read_text(encoding="utf-8").lower()
        assert "chart.umd" not in text and "chart.js" not in text, path
