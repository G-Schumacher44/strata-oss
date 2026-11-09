"""Findings landing page (workbench S5): rows are `triage_rows`, filters and pages are query
strings, PDT pairs group (M2), the page works without JavaScript, and workbench.js never parses
HTML strings."""

from __future__ import annotations

import re
import shutil
import subprocess
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path
from urllib.parse import quote, urlencode

import pytest
from markupsafe import escape

from strata_lookml.cli.dashboard import allowed_hosts
from strata_lookml.outputs.dashboard import NODE_PALETTE
from strata_lookml.pipeline import build_graph
from strata_lookml.triage import TriageRow, TriageStore, triage_rows
from strata_lookml.workbench.app import App, Response
from strata_lookml.workbench.index import Staleness, Workbench, index_graph
from strata_lookml.workbench.pages import findings as page
from strata_lookml.workbench.pages.findings import group_rows
from strata_lookml.workbench.pr_text import CATEGORY_LABELS, pr_comment

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "lookml" / "enterprise_mono"
USAGE = ROOT / "fixtures" / "enterprise_usage_facts.json"
SCHEMA = ROOT / "fixtures" / "enterprise_schema_facts.json"
WORKBENCH_JS = Path(str(resources.files("strata_lookml.assets.js") / "workbench.js"))
PORT = 18766  # a Host string only; App-level tests never bind
HOST = f"127.0.0.1:{PORT}"
PDT = "pdt_attribution_full_funnel"


@pytest.fixture(autouse=True)
def _home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """The triage store and IR cache live under ~/.strata: keep them in a temp HOME."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("STRATA_CACHE_PATH", raising=False)


def _workbench(
    schema: Path | None = SCHEMA,
    baseline: dict[str, set[str]] | None = None,
    base_url: str | None = None,
) -> Workbench:
    graph = build_graph(REPO, USAGE, schema)
    return index_graph(
        graph,
        repo=REPO,
        usage_fixture=str(USAGE),
        schema_fixture=str(schema) if schema else None,
        inputs={},
        baseline=baseline,
        baseline_path="strata-baseline.json" if baseline is not None else None,
        base_url=base_url,
    )


def _app(wb: Workbench) -> App:
    return App(wb, allowed_hosts(PORT), "tok", Staleness(wb.inputs, wb.fingerprint))


def _get(app: App, target: str) -> Response:
    return app.respond("GET", target, HOST)


class _Rows(HTMLParser):
    """Each `data-row`'s attributes, category chips and status, in page order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        cls = a.get("class") or ""
        if "data-row" in a:
            self.rows.append({**a, "cats": [], "status": None})
        elif self.rows and cls.startswith("pill cat-"):
            self.rows[-1]["cats"].append(cls.removeprefix("pill cat-"))
        elif self.rows and cls.startswith("st st-"):
            self.rows[-1]["status"] = cls.removeprefix("st st-")


def _rows(response: Response) -> list[dict]:
    assert response.status == 200, response.body.decode()
    parser = _Rows()
    parser.feed(response.body.decode())
    return parser.rows


def _expected(wb: Workbench) -> list[TriageRow]:
    baseline = None if wb.baseline is None else {k: set(v) for k, v in wb.baseline.items()}
    return triage_rows(wb.graph, baseline, TriageStore.open(wb.repo, wb.graph))


# --- rows are triage_rows ---------------------------------------------------------------------


def test_rows_are_triage_rows_in_order_with_their_status_and_category() -> None:
    graph = build_graph(REPO, USAGE, SCHEMA)
    drift = sorted(
        {
            r.id
            for r in triage_rows(graph, None, TriageStore.open(REPO, graph))
            if r.category == "drift"
        }
    )
    wb = _workbench(baseline={"drift": set(drift[:3]), "dead-code": {"dead:explore:m.gone"}})
    TriageStore.open(REPO, wb.graph).acknowledge(["dead:explore:em_legacy_v1.legacy_orders"])
    expected = _expected(wb)
    shown = _rows(_get(_app(wb), "/findings?status=all"))

    by_id = {r.id: r for r in expected}
    assert [r["data-ids"].split(" ") for r in shown] == [
        [r.id for r in item.rows] for item in group_rows(expected)
    ]
    flat = [i for r in shown for i in r["data-ids"].split(" ")]
    assert sorted(flat) == sorted(by_id), "every triage row is listed exactly once"
    for row in shown:
        members = [by_id[i] for i in row["data-ids"].split(" ")]
        assert {m.status for m in members} == {row["status"]}
        assert row["cats"] == list(dict.fromkeys(m.category for m in members))
    statuses = {r["status"] for r in shown}
    assert {"new", "acknowledged", "baselined", "fixed"} <= statuses


def test_tab_counts_match_the_rows_each_tab_lists() -> None:
    wb = _workbench(baseline={"dead-code": {"dead:explore:m.gone"}})
    app = _app(wb)
    body = _get(app, "/findings").body.decode()
    for key, label in page.STATUS_TABS:
        count = int(re.search(rf">{label} <span class=\"n\">(\d+)</span>", body).group(1))
        assert count == len(_rows(_get(app, f"/findings?status={key}"))), key


# --- filters and pages ------------------------------------------------------------------------


def test_status_category_and_text_filters_come_from_the_query_string() -> None:
    app = _app(_workbench())
    assert {r["status"] for r in _rows(_get(app, "/findings"))} == {"new"}  # landing = new
    drift = _rows(_get(app, "/findings?status=all&category=drift"))
    assert drift and all(r["cats"] == ["drift"] for r in drift)
    # q matches the id, the label and the file, case-insensitively.
    assert [r["data-ids"] for r in _rows(_get(app, "/findings?q=DEAD_FINANCE"))] == [
        "dead:explore:em_legacy_v2.dead_finance_v2"
    ]
    by_file = _rows(_get(app, "/findings?status=all&q=em_legacy_v2.model.lkml"))
    assert len(by_file) == 2 and all("em_legacy_v2" in r["data-ids"] for r in by_file)
    assert _rows(_get(app, "/findings?q=no-such-finding")) == []
    assert "No findings match" in _get(app, "/findings?q=no-such-finding").body.decode()


@pytest.mark.parametrize("query", ["status=nope", "category=nope", "page=0", "page=x"])
def test_unknown_filter_values_are_a_400_page(query: str) -> None:
    assert _get(_app(_workbench()), f"/findings?{query}").status == 400


def test_pages_are_server_side(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(page, "PAGE_SIZE", 5)
    app = _app(_workbench())
    every = [r["data-ids"] for r in _rows(_get(app, "/findings?status=all&page=1"))]
    assert len(every) == 5
    second = [r["data-ids"] for r in _rows(_get(app, "/findings?status=all&page=2"))]
    assert len(second) == 5 and not set(every) & set(second)
    body = _get(app, "/findings?status=all&category=drift&page=2").body.decode()
    assert 'href="/findings?status=all&amp;category=drift&amp;page=3"' in body  # filters kept
    # Past the end clamps to the last page rather than listing nothing.
    total = len(group_rows(_expected(app.workbench)))
    last = _rows(_get(app, "/findings?status=all&page=999"))
    assert len(last) == total - 5 * ((total - 1) // 5)


# --- M2: a PDT reported as dead code and as a zombie is one row --------------------------------


def test_pdt_dead_view_and_zombie_findings_group_into_one_row() -> None:
    rows = _rows(_get(_app(_workbench()), "/findings?status=all"))
    (pair,) = [r for r in rows if PDT in r["data-ids"]]
    assert pair["data-ids"] == f"pdt:{PDT} dead:view:{PDT}"  # ids unchanged
    assert pair["cats"] == ["zombie-pdt", "dead-code"]
    assert pair["data-href"] == f"/finding/pdt%3A{PDT}"
    # The category filter finds the group from either half.
    for category in ("dead-code", "zombie-pdt"):
        filtered = _rows(_get(_app(_workbench()), f"/findings?status=all&category={category}"))
        assert any(r["data-ids"] == pair["data-ids"] for r in filtered), category


def test_a_pdt_pair_in_two_statuses_stays_two_rows() -> None:
    wb = _workbench()
    TriageStore.open(REPO, wb.graph).acknowledge([f"pdt:{PDT}"])
    rows = _rows(_get(_app(wb), "/findings?status=all"))
    halves = [r for r in rows if PDT in r["data-ids"]]
    assert sorted((r["data-ids"], r["status"]) for r in halves) == [
        (f"dead:view:{PDT}", "new"),
        (f"pdt:{PDT}", "acknowledged"),
    ]


def test_grouping_needs_both_halves() -> None:
    def row(i: str, category: str) -> TriageRow:
        return TriageRow(i, category, i, "m", None, None, None, "new")

    alone = [
        row("dead:view:a", "dead-code"),
        row("pdt:b", "zombie-pdt"),
        row("dead:view:b2", "dead-code"),
    ]
    assert [len(item.rows) for item in group_rows(alone)] == [1, 1, 1]
    paired = [row("dead:view:a", "dead-code"), row("x", "drift"), row("pdt:a", "unused-pdt")]
    assert [[r.id for r in i.rows] for i in group_rows(paired)] == [["pdt:a", "dead:view:a"], ["x"]]


# --- statuses the page must never invent --------------------------------------------------------


def test_a_baselined_drift_id_without_schema_facts_is_not_checked_never_fixed() -> None:
    graph = build_graph(REPO, USAGE, SCHEMA)
    drift = next(
        r.id
        for r in triage_rows(graph, None, TriageStore.open(REPO, graph))
        if r.category == "drift"
    )
    app = _app(_workbench(schema=None, baseline={"drift": {drift}}))
    rows = _rows(_get(app, "/findings?status=all"))
    (row,) = [r for r in rows if r["data-ids"] == drift]
    assert row["status"] == "not_checked"
    assert "data-href" not in row  # no current record, so no finding page to open
    assert _rows(_get(app, "/findings?status=fixed")) == []
    assert [r["data-ids"] for r in _rows(_get(app, "/findings?status=not_checked"))] == [drift]
    body = _get(app, "/findings").body.decode()
    assert "schema not run" in body


# --- PR comment text, cost, coverage ------------------------------------------------------------


def _comment(app: App, ids: list[str]) -> Response:
    return _get(app, "/api/pr-comment?" + urlencode([("id", i) for i in ids]))


def test_the_list_copies_the_one_pr_comment_builder() -> None:
    """`c` fetches /api/pr-comment for the row's ids: the text is `pr_text.pr_comment` over
    their records, byte for byte (G19: the list, finding and detail pages share one builder)."""
    wb = _workbench()
    app = _app(wb)
    (pair,) = [r for r in _rows(_get(app, "/findings")) if PDT in r["data-ids"]]
    ids = pair["data-ids"].split(" ")
    response = _comment(app, ids)
    assert response.status == 200
    assert ("Content-Type", "text/plain; charset=utf-8") in response.headers
    assert ("X-Content-Type-Options", "nosniff") in response.headers
    records = [dict(r) for i in ids for r in wb.findings_by_id[i]]
    expected = pr_comment(records, {"kind": "finding", "id": "", "name": ""}, None)
    assert response.body.decode() == expected
    assert expected.startswith("**Strata** found 2 LookML findings:")
    assert f"`pdt:{PDT}`" in expected and f"`dead:view:{PDT}`" in expected


def test_pr_comment_links_only_with_a_workbench_base() -> None:
    plain = _comment(_app(_workbench()), [f"pdt:{PDT}"]).body.decode()
    assert "Workbench:" not in plain
    base = "http://127.0.0.1:8765"
    linked = _comment(_app(_workbench(base_url=base)), [f"pdt:{PDT}"]).body.decode()
    assert f"  - Workbench: {base}/finding/pdt%3A{PDT}" in linked


def test_pr_comment_skips_ids_without_a_current_record() -> None:
    app = _app(_workbench(baseline={"dead-code": {"dead:explore:m.gone"}}))
    assert _comment(app, ["dead:explore:m.gone"]).status == 404  # fixed: nothing to quote
    assert _comment(app, []).status == 404
    mixed = _comment(app, ["dead:explore:m.gone", f"pdt:{PDT}"]).body.decode()
    assert "m.gone" not in mixed and mixed.startswith("**Strata** found 1 LookML finding:")


def test_cost_column_coverage_strip_and_palette() -> None:
    wb = _workbench(baseline={})
    body = _get(_app(wb), "/findings").body.decode()
    assert "Cost / 30d" in body and ">$45,000<" in body
    assert "usage ✓ 30d (2026-05-07 → 2026-06-06)" in body
    assert "schema ✓" in body and "content ✓" in body and "baseline strata-baseline.json" in body
    for key, hex_ in NODE_PALETTE.items():  # status colours come from the one palette
        assert f"--n-{key.replace('_', '-')}: {hex_};" in body


# --- works without JavaScript -----------------------------------------------------------------


def test_page_works_without_javascript() -> None:
    body = _get(_app(_workbench()), "/findings?status=all&category=drift").body.decode()
    # The filter is a GET form that keeps the other filters.
    assert '<form class="filter" method="get" action="/findings"' in body
    assert '<input type="hidden" name="status" value="all">' in body
    assert '<input type="hidden" name="category" value="drift">' in body
    for key, _ in page.STATUS_TABS:  # tabs are links
        assert f'href="/findings?status={key}&amp;category=drift"' in body
    assert 'href="/findings?status=all&amp;category=dead-code"' in body  # chips are links
    rows = _rows(_get(_app(_workbench()), "/findings?status=all"))
    first = rows[0]
    assert (
        f'<a href="{escape(first["data-href"])}"'
        in _get(_app(_workbench()), "/findings").body.decode()
    )
    # JS-only controls ship hidden or disabled, so nothing dead shows without the script.
    assert re.search(r'<div class="actionbar"[^>]* hidden>', body)
    assert re.search(r"data-select disabled>", body)
    assert body.count("<script") == 1 and '<script src="/static/workbench.js" defer>' in body


def test_workbench_assets_are_served_from_the_allow_list() -> None:
    app = _app(_workbench())
    js = _get(app, "/static/workbench.js")
    assert js.status == 200 and ("Content-Type", "text/javascript; charset=utf-8") in js.headers
    assert js.body == WORKBENCH_JS.read_bytes()
    css = _get(app, "/static/workbench.css")
    assert css.status == 200 and ("Content-Type", "text/css; charset=utf-8") in css.headers


def test_hostile_filter_text_is_reflected_escaped() -> None:
    hostile = "<img src=x onerror=alert(1)>\"'"
    body = _get(_app(_workbench()), "/findings?q=" + quote(hostile, safe="")).body.decode()
    assert "<img" not in body
    assert 'value="&lt;img src=x onerror=alert(1)&gt;&#34;&#39;"' in body


# --- workbench.js: no HTML parsing sinks, valid syntax -----------------------------------------

_SINKS = re.compile(
    r"\.(?:innerHTML|outerHTML)\b|insertAdjacentHTML|document\.write|\beval\s*\(|"
    r"new\s+Function\b|createContextualFragment|DOMParser|setAttribute\(\s*[\"']on|"
    r"setTimeout\(\s*[\"'`]|setInterval\(\s*[\"'`]"
)


def _sinks(source: str) -> list[str]:
    """Every HTML-parsing or code-evaluating sink in `source` (an allowlist of none)."""
    return [m.group(0) for m in _SINKS.finditer(source)]


def test_workbench_js_has_no_html_parsing_sinks() -> None:
    assert _sinks(WORKBENCH_JS.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    "planted",
    [
        "el.innerHTML = label;",
        "el.outerHTML = x;",
        "el.insertAdjacentHTML('beforeend', x);",
        "document.write(x);",
        "eval(x);",
        "new Function(x)();",
        "el.setAttribute('onclick', x);",
        "setTimeout('go()', 1);",
    ],
)
def test_the_sink_scan_catches_a_planted_sink(planted: str) -> None:
    """Negative control: each sink, planted in the real file, is found."""
    source = WORKBENCH_JS.read_text(encoding="utf-8")
    assert _sinks(source.replace('"use strict";', '"use strict";\n' + planted, 1))


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_workbench_js_passes_node_check() -> None:
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run([node, "--check", str(WORKBENCH_JS)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_every_finding_category_has_a_label() -> None:
    """A category added to the gate without a label would KeyError every /findings request."""
    assert set(CATEGORY_LABELS) >= set(page.CATEGORIES)


def test_help_dialog_has_a_close_button_that_works_without_javascript() -> None:
    body = _get(_app(_workbench()), "/findings").body.decode()
    dialog = body[body.index('<dialog id="help"') : body.index("</dialog>")]
    assert re.search(
        r'<form method="dialog"[^>]*><button [^>]*type="submit" aria-label="Close help">', dialog
    )


@pytest.mark.parametrize("page_key", ["findings", "overview", "graph", "search"])
def test_each_top_level_page_marks_its_own_nav_link_current(page_key: str) -> None:
    body = _get(_app(_workbench()), f"/{page_key}").body.decode()
    current = re.findall(r'<a class="navlink" href="/(\w+)" aria-current="page">', body)
    assert current == [page_key]
