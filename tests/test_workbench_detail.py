"""Workbench detail pages (S6): shared frame, verdict/action, lineage links, usage, PR comment."""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

import pytest

from strata_lookml.cli.dashboard import allowed_hosts
from strata_lookml.links import finding_path, object_path
from strata_lookml.outputs.artifacts import cleanup_roadmap
from strata_lookml.workbench.app import App, Response
from strata_lookml.workbench.index import Staleness, Workbench, index_graph, load_graph
from strata_lookml.workbench.pr_text import pr_comment

ROOT = Path(__file__).resolve().parent
ENTERPRISE = ROOT / "lookml" / "enterprise_mono"
USAGE = ROOT / "fixtures" / "enterprise_usage_facts.json"
SCHEMA = ROOT / "fixtures" / "enterprise_schema_facts.json"
HOST = "127.0.0.1:18766"
HREF = re.compile(r'href="(/[^"]*)"')


@pytest.fixture(autouse=True)
def _home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("STRATA_CACHE_PATH", raising=False)


def _wb(
    usage: bool = True, schema: bool = True, base: str | None = None, dup: bool = False
) -> Workbench:
    u, s = (str(USAGE) if usage else None), (str(SCHEMA) if schema else None)
    graph, inputs = load_graph(ENTERPRISE, u, s)
    if dup:
        drift = graph.metadata["l1"]["schema_drift"]
        column = next(r for r in drift if r["kind"] == "missing_column")
        drift.append(dict(column, source_file="other.view.lkml"))
    return index_graph(
        graph, repo=ENTERPRISE, usage_fixture=u, schema_fixture=s, inputs=inputs, base_url=base
    )


def _app(wb: Workbench) -> App:
    return App(wb, allowed_hosts(18766), "tok", Staleness(wb.inputs, wb.fingerprint))


def _get(app: App, target: str) -> Response:
    return app.respond("GET", target, HOST)


def _text(r: Response) -> str:
    return r.body.decode("utf-8")


@pytest.fixture
def app() -> App:
    return _app(_wb())


def _page(app: App, target: str) -> str:
    r = _get(app, target)
    assert r.status == 200, (target, _text(r)[:300])
    return _text(r)


def _pr_text(page: str) -> str:
    m = re.search(r'<textarea[^>]*id="pr-text"[^>]*>(.*?)</textarea>', page, re.S)
    assert m
    return unescape(m.group(1))


def _follow(app: App, page: str) -> int:
    n = 0
    for href in set(HREF.findall(unescape(page))):
        if href in ("/findings", "/overview", "/graph", "/search") or href.startswith("/static/"):
            continue
        assert _get(app, href).status in (200, 300), href
        n += 1
    return n


# --- each kind: location, verdict/action, links that resolve ---------------------------------


@pytest.mark.parametrize(
    ("target", "loc", "label"),
    [
        (
            "/explore/em_legacy_v2.dead_finance_v2",
            "models/em_legacy_v2.model.lkml:23",
            "DEPRECATE",
        ),
        (
            "/explore/em_marketing_base.cart_analysis",
            "models/em_marketing_base.model.lkml:22",
            "KEEP",
        ),
        ("/view/legacy_customer_profile", ".view.lkml:", "REVIEW FOR DEPRECATION"),
        ("/view/fct_cart_abandonment", "views/base/fct_cart_abandonment.view.lkml:1", "NO ACTION"),
        (
            "/pdt/pdt_attribution_full_funnel",
            "views/pdts/pdt_attribution_full_funnel.view.lkml:4",
            "REVIEW PDT REBUILD COST",
        ),
        (
            "/table/acme-analytics.gold_marts.fct_cart_abandonment",
            "views/base/fct_cart_abandonment.view.lkml",
            "NO ACTION",
        ),
        (
            "/field/fct_cart_abandonment.cart_date",
            "views/base/fct_cart_abandonment.view.lkml:4",
            "NO ACTION",
        ),
        ("/field/legacy_order_detail.total_unit_cost", ".view.lkml:", "REPAIR SCHEMA REFERENCE"),
    ],
)
def test_each_kind_renders_location_verdict_and_resolvable_links(
    app: App, target: str, loc: str, label: str
) -> None:
    page = _page(app, target)
    assert loc in page
    assert f'<span class="v">{label}</span>' in page
    assert 'data-copy="' in page  # file:line copy button
    assert _follow(app, page) >= 1


def test_explore_verdict_comes_from_the_deterministic_rule(app: App) -> None:
    page = _page(app, "/explore/em_legacy_v2.dead_finance_v2")
    assert "zero usage plus structural/static dead-code evidence" in page
    assert "usage:explore:em_legacy_v2.dead_finance_v2" in page  # evidence chips
    keep = _page(app, "/explore/em_marketing_base.cart_analysis")
    assert "explore has recent usage evidence" in keep


def test_roadmap_action_is_the_public_cleanup_roadmap(app: App) -> None:
    roadmap = cleanup_roadmap(app.workbench.graph.metadata["l1"])
    assert {i["action"] for i in roadmap} >= {"review_for_deprecation", "repair_schema_reference"}


def test_lineage_marks_dead_and_zombie_from_finding_status(app: App) -> None:
    page = _page(app, "/pdt/pdt_attribution_full_funnel")
    assert 'class="pill dead">dead</span>' in page  # the dead explore that reads it
    assert 'href="/explore/em_legacy_v2.dead_finance_v2"' in page
    explore = _page(app, "/explore/em_legacy_v2.dead_finance_v2")
    assert 'class="pill zombie">zombie</span>' in explore  # its joined zombie PDT view


def test_findings_on_the_object_link_to_finding_pages_with_disabled_ack(app: App) -> None:
    page = _page(app, "/explore/em_legacy_v2.dead_finance_v2")
    assert f'href="{finding_path("dead:explore:em_legacy_v2.dead_finance_v2")}"' in page
    assert re.search(r"<button[^>]*disabled[^>]*>Acknowledge</button>", page)
    assert "(S9)" in page


# --- content usage: counts vs not loaded -----------------------------------------------------


def test_content_counts_show_the_window(app: App) -> None:
    page = _page(app, "/explore/em_marketing_base.cart_analysis")
    assert "viewed in 30d" in page
    assert "Cart Abandonment by Channel" in page
    assert "Content usage not loaded" not in page


def test_content_not_loaded_is_never_zero() -> None:
    page = _page(_app(_wb(usage=False)), "/explore/em_marketing_base.cart_analysis")
    assert "Content usage not loaded" in page
    assert "Content references" not in page
    assert "not loaded" in page.split("Queries")[1][:200]  # queries are not a fake 0 either


def test_loaded_content_with_zero_references_is_a_real_zero(app: App) -> None:
    page = _page(app, "/explore/em_legacy_v2.dead_finance_v2")
    assert "Content references" in page and "Content usage not loaded" not in page


# --- PR comment ------------------------------------------------------------------------------

RECORD = {
    "category": "zombie-pdt",
    "id": "pdt:pdt_attribution_full_funnel",
    "message": "zombie PDT, 180 builds",
    "source_file": "views/pdts/pdt_attribution_full_funnel.view.lkml",
    "source_line": 4,
    "evidence_ids": ["pdt:pdt_attribution_full_funnel", "pdt_build:pdt_attribution_full_funnel"],
    "cost_usd": 45000.0,
}
OBJ = {
    "kind": "pdt",
    "id": "pdt:pdt_attribution_full_funnel",
    "name": "pdt_attribution_full_funnel",
}

GOLDEN_NO_BASE = """\
**Strata** found 1 LookML finding on pdt `pdt_attribution_full_funnel`:

- **zombie PDT** `pdt:pdt_attribution_full_funnel`
  - `views/pdts/pdt_attribution_full_funnel.view.lkml:4` — zombie PDT, 180 builds
  - Rebuild cost: $45,000
  - Suggested: Review PDT rebuild cost
  - Evidence: `pdt:pdt_attribution_full_funnel`, `pdt_build:pdt_attribution_full_funnel`"""


def test_pr_comment_golden_without_a_base_has_no_link() -> None:
    assert pr_comment([RECORD], OBJ) == GOLDEN_NO_BASE
    assert "Workbench" not in pr_comment([RECORD], OBJ, None)


def test_pr_comment_golden_with_a_base_links_the_finding() -> None:
    text = pr_comment([RECORD], OBJ, "http://127.0.0.1:8765")
    assert text == GOLDEN_NO_BASE + (
        "\n  - Workbench: http://127.0.0.1:8765/finding/pdt%3Apdt_attribution_full_funnel"
    )


def test_pr_comment_without_findings_is_about_the_object() -> None:
    obj = {
        "kind": "explore",
        "id": "explore:m:e",
        "name": "m.e",
        "source_file": "m.model.lkml",
        "source_line": 3,
    }
    assert pr_comment([], obj, None, ("KEEP", "explore has recent usage evidence")) == (
        "**Strata** on explore `m.e`:\n\n- `m.model.lkml:3`\n- KEEP: explore has recent usage evidence"
    )
    assert pr_comment([], obj, "http://h/wb.html").endswith(
        "- Workbench: http://h/wb.html#/explore/m.e"
    )


def test_page_embeds_the_pr_comment_with_and_without_base() -> None:
    target = "/pdt/pdt_attribution_full_funnel"
    plain = _pr_text(_page(_app(_wb()), target))
    assert "pdt:pdt_attribution_full_funnel" in plain and "Workbench:" not in plain
    based = _pr_text(_page(_app(_wb(base="http://127.0.0.1:8765")), target))
    assert "  - Workbench: http://127.0.0.1:8765/finding/pdt%3Apdt_attribution_full_funnel" in based


# --- finding page ----------------------------------------------------------------------------


def test_duplicate_finding_id_renders_every_record_and_links_the_subject() -> None:
    wb = _wb(dup=True)
    (fid,) = {i for i, v in wb.findings_by_id.items() if len(v) == 2}
    app = _app(wb)
    page = _page(app, finding_path(fid))
    assert page.count("Record ") == 2 and "Record 1 of 2" in page and "Record 2 of 2" in page
    assert "other.view.lkml" in page
    subject = wb.findings_by_id[fid][0]["subject_id"]
    assert f'href="{object_path(subject)}"' in page
    assert _pr_text(page).count(f"`{fid}`") == 2
    assert _follow(app, page) >= 1


def test_single_finding_page_has_verdict_evidence_and_subject(app: App) -> None:
    page = _page(app, finding_path("dead:explore:em_legacy_v2.dead_finance_v2"))
    assert '<span class="v">REVIEW FOR DEPRECATION</span>' in page
    assert 'href="/explore/em_legacy_v2.dead_finance_v2"' in page
    assert _follow(app, page) >= 1


# --- unchanged contract ----------------------------------------------------------------------


def test_ambiguous_and_unknown_names_keep_their_status_codes() -> None:
    app = _app(_wb())
    assert _get(app, "/explore/nope").status == 404
    assert _get(app, "/finding/nope").status == 404
    assert _get(app, "/static/detail.js").status == 200


# --- triage status is triage_rows' ------------------------------------------------------------


def test_status_pill_is_the_real_triage_status(app: App) -> None:
    from strata_lookml.triage import TriageStore

    fid = "dead:explore:em_legacy_v2.dead_finance_v2"
    assert '<span class="pill">new</span>' in _page(app, "/explore/em_legacy_v2.dead_finance_v2")
    TriageStore.open(ENTERPRISE, app.workbench.graph).acknowledge([fid], note="DATA-412 sunset")
    for target in ("/explore/em_legacy_v2.dead_finance_v2", finding_path(fid)):
        page = _page(app, target)  # read fresh: no restart after an ack from the CLI
        assert '<span class="pill">acknowledged</span>' in page, target
        assert "DATA-412 sunset" in page
    assert '<span class="pill">new</span>' not in _page(app, finding_path(fid))


def test_baselined_status_wins_over_new(tmp_path: Path) -> None:
    wb = _wb()
    ids = {"dead-code": {r["id"] for r in wb.records if r["category"] == "dead-code"}}
    based = index_graph(
        wb.graph,
        repo=ENTERPRISE,
        usage_fixture=wb.usage_fixture,
        schema_fixture=wb.schema_fixture,
        inputs=wb.inputs,
        baseline=ids,
    )
    page = _page(_app(based), "/explore/em_legacy_v2.dead_finance_v2")
    assert '<span class="pill">baselined</span>' in page


def test_pdt_without_build_facts_says_not_loaded_never_zero(tmp_path: Path) -> None:
    facts = json.loads(USAGE.read_text())
    facts["pdt_builds"] = [p for p in facts["pdt_builds"] if p["view"] != "pdt_regional_kpi"]
    usage = tmp_path / "usage.json"
    usage.write_text(json.dumps(facts))
    graph, inputs = load_graph(ENTERPRISE, str(usage), str(SCHEMA))
    wb = index_graph(
        graph,
        repo=ENTERPRISE,
        usage_fixture=str(usage),
        schema_fixture=str(SCHEMA),
        inputs=inputs,
    )
    page = _page(_app(wb), "/pdt/pdt_regional_kpi")
    assert "not loaded for this PDT" in page
    assert "$0" not in page
    assert "Builds" not in page.split("Details")[1].split("Upstream")[0]


def test_roadmap_actions_match_by_node_identity_not_name(tmp_path: Path) -> None:
    """Table `sales.orders` and explore `sales.orders` share a dotted name: only the explore
    carries the dead-explore action."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "sales.model.lkml").write_text(
        'connection: "c"\ninclude: "*.view.lkml"\nexplore: orders { from: v }\n', encoding="utf-8"
    )
    (repo / "v.view.lkml").write_text(
        "view: v {\n  sql_table_name: sales.orders ;;\n  dimension: id { sql: ${TABLE}.id ;; }\n}\n",
        encoding="utf-8",
    )
    usage = tmp_path / "usage.json"
    usage.write_text(
        json.dumps({"explore_usage": [], "content_references": [], "pdt_builds": []}),
        encoding="utf-8",
    )
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps({"tables": [{"name": "sales.orders", "columns": ["id"]}]}), encoding="utf-8"
    )
    graph, inputs = load_graph(repo, str(usage), str(schema))
    wb = index_graph(
        graph, repo=repo, usage_fixture=str(usage), schema_fixture=str(schema), inputs=inputs
    )
    app = _app(wb)
    roadmap = cleanup_roadmap(graph.metadata["l1"])
    assert [i["target"] for i in roadmap] == ["sales.orders", "v"], "fixture: dead explore + view"
    assert '<span class="v">NO ACTION</span>' in _page(app, "/table/sales.orders")
    explore = _page(app, "/explore/sales.orders")
    assert '<span class="v">DEPRECATE</span>' in explore
    assert "REVIEW FOR DEPRECATION" in _page(app, "/view/v")  # its own record, by its own id
