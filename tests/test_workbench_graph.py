"""Graph drill-in, ⌘K and the shared theme palette (workbench S8): the focus neighbourhood (M4),
`/api/graph`, `/api/index.json`, `/search`, the palette's fuzzy scorer, the graph-data dead
flags (G15), and the detail / overview pages reading the theme tokens (G18)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from importlib import resources
from pathlib import Path

import pytest

from strata_lookml.cli.dashboard import allowed_hosts
from strata_lookml.links import graph_path, object_path
from strata_lookml.outputs.artifacts import build_artifacts
from strata_lookml.pipeline import build_graph
from strata_lookml.workbench import app as app_module
from strata_lookml.workbench.app import App, Response
from strata_lookml.workbench.graph import (
    EDGE_LEGEND,
    EDGE_PALETTE,
    NODE_LEGEND,
    NODE_PALETTE,
    build_graph_data,
    edge_var,
    neighbourhood,
    node_var,
)
from strata_lookml.workbench.index import Staleness, Workbench, index_graph
from strata_lookml.workbench.jump import fuzzy, search
from tests.test_workbench_findings import _sinks

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "lookml" / "enterprise_mono"
USAGE = ROOT / "fixtures" / "enterprise_usage_facts.json"
SCHEMA = ROOT / "fixtures" / "enterprise_schema_facts.json"
GCS = ROOT / "lookml" / "gcs_analytics"
JS = resources.files("strata_lookml.assets.js")
GRAPH_JS = Path(str(JS / "graph.js"))
WORKBENCH_JS = Path(str(JS / "workbench.js"))
CSS = Path(str(resources.files("strata_lookml.assets.css") / "workbench.css"))
TEMPLATES = Path(str(resources.files("strata_lookml.workbench") / "templates"))
PORT = 18767  # a Host string only; App-level tests never bind
HOST = f"127.0.0.1:{PORT}"
FOCUS = "view:int_attributed_purchases"


@pytest.fixture(autouse=True)
def _home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """The triage store and IR cache live under ~/.strata: keep them in a temp HOME."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("STRATA_CACHE_PATH", raising=False)


@pytest.fixture(scope="module")
def graph():
    return build_graph(REPO, USAGE, SCHEMA)


@pytest.fixture(scope="module")
def data(graph):
    return build_graph_data(graph)


def _app(graph) -> App:
    wb: Workbench = index_graph(
        graph, repo=REPO, usage_fixture=str(USAGE), schema_fixture=str(SCHEMA), inputs={}
    )
    return App(wb, allowed_hosts(PORT), "tok", Staleness(wb.inputs, wb.fingerprint))


@pytest.fixture
def app(graph) -> App:
    return _app(graph)


def _get(app: App, target: str, host: str | None = HOST) -> Response:
    return app.respond("GET", target, host)


def _ids(hood) -> dict[str, str]:
    return {n["data"]["id"]: n["data"]["ring"] for n in hood["nodes"]}


# --- the focus neighbourhood (M4) ------------------------------------------------------------


def test_one_hop_is_both_directions_and_matches_the_lookml(data) -> None:
    """Hand-computed from enterprise_mono: int_attributed_purchases reads one table
    (views/base/int_attributed_purchases.view.lkml:2) and is the base view of six explores
    (em_orders_base orders + order_detail, em_legacy_v2 dead_orders_v2, and the three regional
    explores that extend em_orders_base.orders)."""
    hood = neighbourhood(data, FOCUS)
    assert _ids(hood) == {
        FOCUS: "focus",
        "physical_table:acme-analytics.silver.int_attributed_purchases": "upstream 1",
        "explore:em_orders_base:orders": "downstream 1",
        "explore:em_orders_base:order_detail": "downstream 1",
        "explore:em_legacy_v2:dead_orders_v2": "downstream 1",
        "explore:em_analytics_eu:orders_eu": "downstream 1",
        "explore:em_analytics_us:orders_us": "downstream 1",
        "explore:em_data_science:orders_ds": "downstream 1",
    }
    assert hood["total"] == hood["shown"] == 8
    # Edges are exactly the graph edges between kept nodes.
    kept = set(_ids(hood))
    expected = {
        (e["data"]["source"], e["data"]["target"])
        for e in data["edges"]
        if e["data"]["source"] in kept and e["data"]["target"] in kept
    }
    assert {(e["data"]["source"], e["data"]["target"]) for e in hood["edges"]} == expected


def test_second_hop_and_siblings_are_opt_in_per_direction(data) -> None:
    explore = "explore:em_orders_base:orders"
    one = _ids(neighbourhood(data, explore))
    assert set(one.values()) == {"focus", "upstream 1"}  # an explore has nothing reading it
    up2 = _ids(neighbourhood(data, explore, up=2))
    assert "physical_table:acme-analytics.silver.int_attributed_purchases" in up2
    assert set(up2.values()) == {"focus", "upstream 1", "upstream 2"}
    assert _ids(neighbourhood(data, explore, down=2)) == one  # down alone adds nothing here
    # Siblings: the other views the focus view's explores join.
    plain = _ids(neighbourhood(data, FOCUS))
    with_siblings = _ids(neighbourhood(data, FOCUS, siblings=True))
    added = {k: v for k, v in with_siblings.items() if k not in plain}
    assert added and set(added.values()) == {"siblings"}
    assert "view:fct_daily_dashboard" in added


def test_cap_keeps_rings_in_order_and_reports_the_total(data) -> None:
    full = neighbourhood(data, FOCUS, up=2, down=2, siblings=True)
    capped = neighbourhood(data, FOCUS, up=2, down=2, siblings=True, cap=4)
    assert capped["shown"] == 4 and capped["total"] == full["total"] > 4
    assert [n["data"]["id"] for n in capped["nodes"]] == [
        n["data"]["id"] for n in full["nodes"][:4]
    ]
    assert capped["nodes"][0]["data"]["focus"] is True
    assert neighbourhood(data, "view:nope") is None


def test_graph_page_notes_a_capped_neighbourhood(graph, monkeypatch: pytest.MonkeyPatch) -> None:
    assert "Showing" not in _get(_app(graph), graph_path(FOCUS)).body.decode()  # 8 < 40
    monkeypatch.setattr(app_module, "NODE_CAP", 3)
    capped = _get(_app(graph), graph_path(FOCUS))
    assert "Showing 3 of 8 nodes (capped at 3)" in capped.body.decode()
    assert json.loads(_get(_app(graph), "/api" + graph_path(FOCUS)).body)["shown"] == 3


# --- /graph and /api/graph ---------------------------------------------------------------------


def test_api_graph_is_json_host_checked_and_nosniff(app: App) -> None:
    r = _get(app, "/api" + graph_path(FOCUS))
    headers = dict(r.headers)
    assert r.status == 200
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert headers["X-Content-Type-Options"] == "nosniff"
    payload = json.loads(r.body)
    assert set(payload) == {
        "focus",
        "up",
        "down",
        "siblings",
        "total",
        "shown",
        "cap",
        "nodes",
        "edges",
    }
    assert (payload["focus"], payload["up"], payload["down"], payload["siblings"]) == (
        FOCUS,
        1,
        1,
        False,
    )
    focus = payload["nodes"][0]["data"]
    assert focus["focus"] is True and focus["path"] == "/view/int_attributed_purchases"
    for node in payload["nodes"]:
        assert node["data"]["path"] == object_path(node["data"]["id"])
        assert node["data"]["color"] in NODE_PALETTE.values()
        assert node["data"]["caption"]
    foreign = _get(app, "/api" + graph_path(FOCUS), host="evil.example:80")
    assert foreign.status == 403 and b"focus" not in foreign.body
    assert _get(app, "/api/graph?focus=view%3Anope").status == 404
    assert _get(app, "/api/graph?focus=" + FOCUS + "&hops=3").status == 400
    assert _get(app, "/api/graph?focus=" + FOCUS + "&siblings=yes").status == 400


def test_graph_page_lists_the_neighbourhood_without_javascript(app: App) -> None:
    body = _get(app, graph_path(FOCUS)).body.decode()
    hood = json.loads(_get(app, "/api" + graph_path(FOCUS)).body)
    for node in hood["nodes"]:
        assert f'href="{node["data"]["path"]}"' in body  # every node links to its page
    assert 'data-src="/api/graph?focus=view%3Aint_attributed_purchases&amp;hops=1"' in body
    assert "data-graph-canvas" in body and "data-graph-list" in body
    for script in ("cytoscape.min.js", "dagre.min.js", "cytoscape-dagre.min.js", "graph.js"):
        assert body.count(f'<script src="/static/{script}" defer></script>') == 1
        assert _get(app, f"/static/{script}").status == 200
    assert "<script>" not in body  # never inline JSON or code
    # The per-direction controls flip one direction and keep the other.
    assert 'href="/graph?focus=view%3Aint_attributed_purchases&amp;up=2&amp;down=1"' in body
    assert 'href="/graph?focus=view%3Aint_attributed_purchases&amp;hops=1&amp;siblings=1"' in body


def test_graph_without_a_focus_offers_explores(app: App) -> None:
    body = _get(app, "/graph").body.decode()
    assert 'href="/graph?focus=explore%3Aem_orders_base%3Aorders&amp;hops=1"' in body
    assert "data-graph-canvas" not in body


def test_detail_pages_link_into_the_graph_when_it_draws_the_node(app: App) -> None:
    assert 'href="/graph?focus=view%3Aint_attributed_purchases&amp;hops=1"' in (
        _get(app, "/view/int_attributed_purchases").body.decode()
    )
    field = next(n for n in app.workbench.graph.nodes.values() if n.kind == "field")
    path = object_path(field.id)
    assert path and "Open in graph" not in _get(app, path).body.decode()  # fields are not drawn


def test_legend_covers_both_palettes_from_their_custom_properties(app: App) -> None:
    assert set(NODE_LEGEND) == set(NODE_PALETTE)
    assert set(EDGE_LEGEND) == set(EDGE_PALETTE)
    body = _get(app, graph_path(FOCUS)).body.decode()
    for key, hex_ in NODE_PALETTE.items():
        assert f"--{node_var(key)}: {hex_};" in body
        assert f".key-{node_var(key)} {{ background:var(--{node_var(key)}); }}" in body
        assert f'class="sw key-{node_var(key)}"' in body
    for relation in EDGE_PALETTE:
        assert f'class="ln key-{edge_var(relation)}"' in body
    assert "explore, usage not loaded" in body  # the explore_unknown state (S11/#75)


# --- G15: dead flags read the register by kind ------------------------------------------------


@pytest.mark.parametrize(
    ("repo", "usage", "schema"),
    [
        (REPO, USAGE, SCHEMA),
        (
            GCS,
            ROOT / "fixtures" / "gcs_usage_facts.json",
            ROOT / "fixtures" / "gcs_schema_facts.json",
        ),
    ],
)
def test_dead_flags_match_the_register_by_kind(repo: Path, usage: Path, schema: Path) -> None:
    """G15 closed as not-a-bug: the register keys explores by `model.explore` (always dotted)
    and views by bare name (never dotted), so graph data's two lookups cannot cross."""
    g = build_graph(repo, usage, schema)
    register = g.metadata["l1"]["dead_code"]
    assert {r["kind"] for r in register} <= {"explore", "view"}
    assert all("." in r["name"] for r in register if r["kind"] == "explore")
    assert not any("." in r["name"] for r in register if r["kind"] == "view")
    nodes = [n["data"] for n in build_graph_data(g)["nodes"]]
    dead = {
        (n["kind"], f"{n['model']}.{n['label']}" if n["kind"] == "explore" else n["label"])
        for n in nodes
        if n["dead"] and n["kind"] in {"explore", "view"}
    }
    assert dead == {(r["kind"], r["name"]) for r in register}
    assert any(kind == "explore" for kind, _ in dead), "the fixture must have a dead explore"


# --- ⌘K index and /search ----------------------------------------------------------------------


def test_index_holds_every_catalog_object_and_every_finding(app: App, graph) -> None:
    payload = json.loads(_get(app, "/api/index.json").body)
    items = payload["items"]
    assert all(set(i) == {"id", "kind", "label", "path"} for i in items)
    assert set(payload["kinds"]) >= {i["kind"] for i in items}
    ids = {i["id"] for i in items}
    paged = {c["id"] for c in build_artifacts(graph)["catalog"] if object_path(c["id"])}
    assert paged and paged <= ids
    assert set(app.workbench.findings_by_id) <= ids
    by_id = {i["id"]: i for i in items}
    assert by_id["explore:em_orders_base:orders"]["label"] == "em_orders_base.orders"
    for finding_id in app.workbench.findings_by_id:
        assert by_id[finding_id]["kind"] == "finding"


def test_search_is_the_server_side_palette(app: App) -> None:
    body = _get(app, "/search?q=lgcy+ord").body.decode()
    first = re.search(r'<li><a class="mono" href="([^"]+)">', body)
    assert first and first.group(1) == "/view/legacy_order_detail"
    assert "<mark>" in body
    assert "Nothing matches" in _get(app, "/search?q=zzzqqq").body.decode()
    empty = _get(app, "/search").body.decode()
    assert '<form class="filter search-form" method="get" action="/search"' in empty
    assert 'class="links results"' not in empty
    results, total = search([{"label": "a"}] * 60, "a")  # type: ignore[list-item]
    assert len(results) == 50 and total == 60


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_palette_fuzzy_scorer_matches_the_server(tmp_path: Path) -> None:
    """workbench.js `fuzzyMatch` and jump.py `fuzzy` rank alike: same matches, scores, hits."""
    source = WORKBENCH_JS.read_text(encoding="utf-8")
    js = re.search(r"// <fuzzy>.*?\n(.*?)// </fuzzy>", source, re.S)
    assert js, "the <fuzzy> markers around fuzzyMatch are missing"
    cases = [
        ("lgcy ord", "legacy_order_detail"),
        ("ord", "em_orders_base.orders"),
        ("EOB", "em_orders_base.orders"),
        ("dead:view", "dead:view:legacy_order_detail"),
        ("xyz", "legacy_order_detail"),
        ("", "anything"),
        ("a a", "a.b_a"),
    ]
    script = tmp_path / "fuzzy.js"
    script.write_text(
        js.group(1)
        + f"\nconsole.log(JSON.stringify({json.dumps(cases)}.map(c => fuzzyMatch(c[0], c[1]))));\n"
    )
    node = shutil.which("node")
    assert node is not None
    out = subprocess.run([node, str(script)], capture_output=True, text=True, check=True).stdout
    for (query, text), got in zip(cases, json.loads(out), strict=True):
        want = fuzzy(query, text)
        if want is None:
            assert got is None, (query, text)
        else:
            assert got is not None, (query, text)
            assert got["hits"] == want[1] and got["score"] == pytest.approx(want[0])


@pytest.mark.parametrize("path", [GRAPH_JS, WORKBENCH_JS], ids=lambda p: p.name)
def test_page_scripts_have_no_html_parsing_sinks(path: Path) -> None:
    assert _sinks(path.read_text(encoding="utf-8")) == []


@pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")
def test_graph_js_passes_node_check() -> None:
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run([node, "--check", str(GRAPH_JS)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# --- G18: every page reads the shared theme tokens ----------------------------------------------

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _hex_colours(text: str) -> list[str]:
    return _HEX.findall(text)


def test_overview_and_detail_carry_no_palette_of_their_own(app: App) -> None:
    for name in (
        "overview.html",
        "_detail_frame.html",
        "detail.html",
        "finding.html",
        "graph.html",
    ):
        source = (TEMPLATES / name).read_text(encoding="utf-8")
        assert _hex_colours(source) == [], name
        assert "prefers-color-scheme" not in source, name
    for target in ("/overview", "/view/int_attributed_purchases"):
        body = _get(app, target).body.decode()
        assert "prefers-color-scheme" not in body
        # The only colours on the page are the palette's custom properties.
        palette = set(NODE_PALETTE.values()) | set(EDGE_PALETTE.values())
        assert set(_hex_colours(body)) <= {h.lower() for h in palette} | palette, target


def test_the_hex_scan_catches_a_planted_palette() -> None:
    """Negative control: an inline palette like the one G18 removed is found."""
    planted = "<style>.detail { --bg:#121820; --dead:#f06b5d; }</style>"
    assert _hex_colours(planted) == ["#121820", "#f06b5d"]


def _block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{(.*?)\}", css, re.S)
    assert match, selector
    return match.group(1)


def test_light_theme_redefines_every_colour_the_overview_and_detail_read() -> None:
    """The toggle flips data-theme on <html>; a colour token those pages use but the light
    block leaves alone would stay dark."""
    css = CSS.read_text(encoding="utf-8")
    light = set(re.findall(r"--([\w-]+)\s*:", _block(css, ':root[data-theme="light"]')))
    start = css.index("/* ---------- Detail pages (S6) ---------- */")
    end = css.index("/* ---------- Graph (S8) ---------- */")
    used = set(re.findall(r"var\(--([\w-]+)", css[start:end]))
    layout_only = {"mono", "sans", "r", "r-lg", "vc"}  # fonts, radii, the verdict's local colour
    assert used - layout_only, "the sections must read theme tokens"
    assert used - layout_only <= light, (used - layout_only) - light
