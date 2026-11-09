"""The static export (workbench S10): one file, the live server's pages byte for byte, no writes.

The export is `workbench/export.py` over a read-only `App`; the browser half is
`assets/js/router.js` (routes), `graph.js` (`neighbourhood`) and `workbench.js`. The router's
and graph's pure parts sit between marker comments and run here under node against the same
data the Python side produces.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterator, Mapping
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path
from typing import Any

import pytest

from strata_lookml.cli.dashboard import allowed_hosts
from strata_lookml.links import finding_path, graph_path
from strata_lookml.triage import TriageStore, triage_rows
from strata_lookml.workbench.app import App
from strata_lookml.workbench.export import EXPORT_HOST, SCRIPTS, export, export_data, page
from strata_lookml.workbench.graph import (
    EXPORT_EDGE_KEYS,
    EXPORT_NODE_KEYS,
    NODE_CAP,
    NODE_PALETTE,
    neighbourhood,
    node_var,
)
from strata_lookml.workbench.index import Staleness, Workbench, index_graph, load_graph
from strata_lookml.workbench.pr_text import pr_comment
from tests.scale_fixture import generate
from tests.test_workbench_findings import _sinks
from tests.test_workbench_server import _hostile_repo

ROOT = Path(__file__).resolve().parent
REPO = ROOT / "lookml" / "enterprise_mono"
USAGE = ROOT / "fixtures" / "enterprise_usage_facts.json"
SCHEMA = ROOT / "fixtures" / "enterprise_schema_facts.json"
TWIN = ROOT / "lookml" / "twin_models"
JS = resources.files("strata_lookml.assets.js")
ROUTER_JS = Path(str(JS / "router.js"))
GRAPH_JS = Path(str(JS / "graph.js"))
PORT = 18768  # a Host string only; never bound
HOST = f"127.0.0.1:{PORT}"
# Ids `index_graph` will find baselined: two current dead-code findings and one long gone, so
# the Baselined and Fixed tabs both have rows.
BASELINE = {
    "dead-code": {
        "dead:explore:em_legacy_v2.dead_finance_v2",
        "dead:explore:em_legacy_v1.legacy_orders",
        "dead:explore:em_legacy_v1.retired_long_ago",
    }
}
_TEMPLATE = re.compile(
    r'<template data-route="([^"]*)" data-title="([^"]*)">(.*?)</template>', re.S
)
_MAIN = re.compile(r"<main>(.*)</main>", re.S)
node_required = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


@pytest.fixture(autouse=True)
def _home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """The IR cache and the triage store live under ~/.strata: keep both in a temp HOME."""
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.delenv("STRATA_CACHE_PATH", raising=False)


def _workbench(
    repo: Path,
    usage: Path | None = None,
    schema: Path | None = None,
    baseline: Mapping[str, set[str]] | None = None,
    base_url: str | None = None,
) -> Workbench:
    graph, inputs = load_graph(repo, str(usage) if usage else None, str(schema) if schema else None)
    return index_graph(
        graph,
        repo=repo,
        usage_fixture=str(usage) if usage else None,
        schema_fixture=str(schema) if schema else None,
        inputs=inputs,
        baseline=baseline,
        base_url=base_url,
    )


def _live(wb: Workbench) -> App:
    """The live server's app (with a triage store) for the same workbench."""
    return App(wb, allowed_hosts(PORT), "token", Staleness(wb.inputs, wb.fingerprint))


def _read_only(wb: Workbench) -> App:
    return App(wb, frozenset({HOST}), "", Staleness(wb.inputs, wb.fingerprint), read_only=True)


def _templates(document: str) -> dict[str, tuple[str, str]]:
    return {
        html.unescape(route): (html.unescape(title), inner)
        for route, title, inner in _TEMPLATE.findall(document)
    }


def _data(document: str) -> dict[str, Any]:
    found = re.search(
        r'<script type="application/json" id="strata-export-data">(.*?)</script>', document, re.S
    )
    assert found
    return json.loads(found.group(1))


def _live_main(app: App, route: str) -> str:
    body = app.respond("GET", route, HOST).body.decode("utf-8")
    found = _MAIN.search(body)
    assert found, route
    return found.group(1)


@pytest.fixture(scope="module")
def enterprise(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Workbench, str]]:
    # Module scope runs before the function-scoped temp HOME: set its own.
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", str(tmp_path_factory.mktemp("home")))
        mp.delenv("STRATA_CACHE_PATH", raising=False)
        wb = _workbench(REPO, USAGE, SCHEMA, BASELINE, base_url="https://acme.example/strata.html")
        yield wb, export(wb)


@pytest.fixture
def hostile(tmp_path: Path) -> tuple[Workbench, str]:
    wb = _workbench(*_hostile_repo(tmp_path))
    return wb, export(wb)


def _run_node(tmp_path: Path, source: str, name: str) -> Any:
    script = tmp_path / name
    script.write_text(source, encoding="utf-8")
    node = shutil.which("node")
    assert node is not None
    out = subprocess.run([node, str(script)], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _between(path: Path, marker: str) -> str:
    found = re.search(
        rf"// <{marker}>.*?\n(.*?)// </{marker}>", path.read_text(encoding="utf-8"), re.S
    )
    assert found, f"the <{marker}> markers are missing from {path.name}"
    return found.group(1)


# --- one renderer: every template is the server's page ------------------------------------------


@pytest.mark.parametrize("fixture", ["enterprise", "hostile"])
def test_every_template_is_the_live_page_byte_for_byte(
    fixture: str, request: pytest.FixtureRequest
) -> None:
    wb, document = request.getfixturevalue(fixture)
    templates = _templates(document)
    live = _live(wb)
    routes = live.export_routes()
    assert list(templates) == routes
    for route, (_title, inner) in templates.items():
        response = live.respond("GET", route, HOST)
        assert response.status in (200, 300), route
        assert inner == _live_main(live, route), route
    data = _data(document)
    for alias, (target, *_) in data["aliases"].items():  # `/findings` is `/findings?status=new`
        if not alias.startswith("/field/"):
            assert _live_main(live, alias if alias != "/" else "/findings") == templates[target][1]


def test_the_export_holds_every_page_kind(enterprise: tuple[Workbench, str]) -> None:
    wb, document = enterprise
    routes = list(_templates(document))
    kinds = {r.split("?")[0].split("/")[1] for r in routes}
    assert kinds == {
        "findings",
        "overview",
        "graph",
        "search",
        "explore",
        "view",
        "pdt",
        "table",
        "finding",
    }
    assert not any(r.startswith("/field/") for r in routes)  # D7: fields live on view pages
    # Each status tab with each category chip, every finding and object page.
    assert "/findings?status=baselined&category=dead-code" in routes
    assert "/findings?status=fixed" in routes
    assert {finding_path(i) for i in wb.findings_by_id} <= set(routes)
    assert sum(r.startswith("/graph?") for r in routes) == 1  # the one focused graph page


def test_baselined_and_fixed_come_from_the_baseline(enterprise: tuple[Workbench, str]) -> None:
    _wb, document = enterprise
    templates = _templates(document)
    baselined = templates["/findings?status=baselined"][1]
    assert "em_legacy_v2.dead_finance_v2" in baselined and "st-baselined" in baselined
    assert "dead:explore:em_legacy_v1.retired_long_ago" in templates["/findings?status=fixed"][1]
    assert (
        'class="tab" href="/findings?status=acknowledged" data-key="2">Acknowledged <span class="n">0<'
        in baselined
    )


def test_view_pages_list_their_fields_and_field_links_alias_to_them(
    enterprise: tuple[Workbench, str],
) -> None:
    wb, document = enterprise
    templates = _templates(document)
    data = _data(document)
    view = templates["/view/fct_cart_abandonment"][1]
    assert (
        '<li data-field="abandoned_carts"><a class="mono" href="/field/fct_cart_abandonment.abandoned_carts">'
        in view
    )
    assert data["aliases"]["/field/fct_cart_abandonment.abandoned_carts"] == [
        "/view/fct_cart_abandonment",
        "abandoned_carts",
    ]
    fields = [i for i in data["index"]["items"] if i["kind"] == "field"]
    assert fields and all(f["path"] in data["aliases"] for f in fields)


def test_export_is_deterministic(enterprise: tuple[Workbench, str]) -> None:
    wb, document = enterprise
    assert export(wb) == document


# --- read-only: no store, no writes, no triage controls ---------------------------------------


def _tree(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_export_writes_nothing_and_never_observes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    shutil.copytree(REPO, repo)
    wb = _workbench(repo, USAGE, SCHEMA)
    store = TriageStore.open(repo, wb.graph)
    present = "dead:explore:em_legacy_v2.dead_finance_v2"
    store.acknowledge([present], "looked at it")
    # An acknowledged id that is gone: `observe` would stamp `first_absent_at` on it.
    document = store.snapshot()
    document["ids"]["dead:explore:em_legacy_v1.gone"] = {
        "category": "dead-code",
        "acked_at": "2026-01-01T00:00:00+00:00",
    }
    document["rev"] += 1
    store.path.write_text(json.dumps(document), encoding="utf-8")
    home = Path(os.environ["HOME"]) / ".strata"
    before_home, before_repo = _tree(home), _tree(repo)
    assert store.path.is_file() and str(store.path.relative_to(home)) in before_home

    exported = export(wb)

    assert _tree(home) == before_home
    assert _tree(repo) == before_repo
    # Statuses come from the baseline alone: the acknowledgement is not in the export.
    findings = _templates(exported)["/findings?status=new"][1]
    assert 'Acknowledged <span class="n">0<' in findings
    assert '<meta name="strata-token" content=' not in exported

    # Negative control: the live path (triage_rows with the store) does write here.
    triage_rows(wb.graph, None, store)
    assert _tree(home) != before_home


def test_read_only_app_refuses_the_triage_post(enterprise: tuple[Workbench, str]) -> None:
    wb, _ = enterprise
    response = _read_only(wb).respond("POST", "/api/triage", HOST)
    assert response.status == 405
    assert dict(response.headers)["Allow"] == "GET, HEAD"


# --- the file: CSP, inline scripts, embedded data -----------------------------------------------


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.top: list[tuple[str, dict[str, str | None]]] = []
        self.depth = 0
        self.in_template = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "template":
            self.in_template += 1
        elif not self.in_template and tag in (
            "script",
            "style",
            "link",
            "meta",
            "template",
            "img",
            "iframe",
        ):
            self.top.append((tag, dict(attrs)))

    def handle_endtag(self, tag: str) -> None:
        if tag == "template":
            self.in_template -= 1


@pytest.mark.parametrize("fixture", ["enterprise", "hostile"])
def test_nothing_breaks_out_of_a_template_or_a_script(
    fixture: str, request: pytest.FixtureRequest
) -> None:
    wb, document = request.getfixturevalue(fixture)
    parser = _Tags()
    parser.feed(document)
    assert parser.in_template == 0
    scripts = [attrs for tag, attrs in parser.top if tag == "script"]
    # The JSON payload and exactly the packaged scripts; no element outside a template came
    # from LookML text (a breakout would add a script, an img or close a template early).
    assert scripts == [{"type": "application/json", "id": "strata-export-data"}] + [{}] * len(
        SCRIPTS
    )
    assert not [tag for tag, _ in parser.top if tag in ("img", "iframe", "link")]
    markup = re.sub(r"<script>.*?</script>", "", document, flags=re.S)  # script text is not markup
    assert len(_TEMPLATE.findall(document)) == markup.count("<template ")
    payload = re.search(r'id="strata-export-data">(.*?)</script>', document, re.S)
    assert payload and "<" not in payload.group(1)


def test_csp_allows_exactly_the_inline_scripts_and_no_network(
    enterprise: tuple[Workbench, str],
) -> None:
    _, document = enterprise
    csp = html.unescape(
        re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', document).group(1)
    )  # type: ignore[union-attr]
    bodies = re.findall(r"<script>(.*?)</script>", document, re.S)
    hashes = {
        "'sha256-" + base64.b64encode(hashlib.sha256(b.encode("utf-8")).digest()).decode() + "'"
        for b in bodies
    }
    assert len(bodies) == len(SCRIPTS)
    script_src = re.search(r"script-src ([^;]*)", csp).group(1).split()  # type: ignore[union-attr]
    assert set(script_src) == hashes
    assert "default-src 'none'" in csp and "connect-src" not in csp  # so fetch() is refused
    assert "unsafe-inline" not in re.search(r"script-src[^;]*", csp).group(0)  # type: ignore[union-attr]


def test_embedded_data_is_what_the_live_api_serves(enterprise: tuple[Workbench, str]) -> None:
    wb, document = enterprise
    data = _data(document)
    live = _live(wb)
    index = json.loads(live.respond("GET", "/api/index.json", HOST).body)
    assert data["index"] == index  # ⌘K offline: the same index /api/index.json serves
    assert data["cap"] == NODE_CAP
    ids = [n["id"] for n in data["graph"]["nodes"]]
    assert ids == sorted(ids) and set(data["graph"]["nodes"][0]) == set(EXPORT_NODE_KEYS)
    assert set(data["graph"]["edges"][0]) == set(EXPORT_EDGE_KEYS)
    for node in data["graph"]["nodes"]:
        assert node["graph"] == graph_path(node["id"])


def test_the_palette_tokens_and_legend_keys_reach_the_export(
    enterprise: tuple[Workbench, str],
) -> None:
    _, document = enterprise
    for key, hex_ in NODE_PALETTE.items():
        assert f"--{node_var(key)}: {hex_};" in document
        assert f".key-{node_var(key)} {{ background:var(--{node_var(key)}); }}" in document


# --- the browser half, under node ---------------------------------------------------------------


@node_required
def test_router_resolves_every_link_and_old_fragments(
    enterprise: tuple[Workbench, str], tmp_path: Path
) -> None:
    wb, document = enterprise
    templates = _templates(document)
    data = _data(document)
    hrefs = sorted(
        {
            html.unescape(h)
            for _, inner in templates.values()
            for h in re.findall(r'href="(/[^"]*)"', inner)
        }
    )
    finding = "dead:explore:em_legacy_v2.dead_finance_v2"
    drift = next(i for i in wb.findings_by_id if i.startswith("schema:"))
    old = {
        # openHashTarget: decoded first, raw second; ids, roadmap: anchors, duplicates, sections
        "encoded": finding.replace(":", "%3A"),
        "raw": finding,
        "drift": drift,
        "drift-dup": drift + ":2",
        "roadmap": "roadmap:explore:em_legacy_v2:dead_finance_v2",
        "roadmap-dup": "roadmap:explore:em_legacy_v2:dead_finance_v2:3",
        "roadmap-unknown": "roadmap:field:nowhere.x",
        "section": "drift",
        "object": "view:fct_cart_abandonment",
        "bad-escape": "%E0%A4%A",
        "unknown": "nothing-here",
    }
    graph_node = data["graph"]["nodes"][5]
    extra = {
        "variant": graph_node["graph"].replace("hops=1", "up=2&down=1") + "&siblings=1",
        "browser-encoded": "/graph?focus=" + graph_node["id"].replace(":", "%3A") + "&hops=2",
        "bad-hops": graph_node["graph"].replace("hops=1", "hops=3"),
        "unknown-focus": "/graph?focus=view%3Anope&hops=1",
        "search": "/search?q=lgcy+ord",
        "filter": "/findings?status=baselined&category=dead-code&q=legacy",
        "missing": "/view/nope",
    }
    source = (
        _between(ROUTER_JS, "routes")
        + f"const r = makeRoutes({json.dumps(data)}, {json.dumps(list(templates))});\n"
        + f"const hrefs = {json.dumps(hrefs)}, old = {json.dumps(old)}, extra = {json.dumps(extra)};\n"
        + "const out = {unresolved: hrefs.filter(h => !r.resolve(h)), old: {}, extra: {}};\n"
        + "for (const k in old) out.old[k] = r.legacy(old[k]);\n"
        + "for (const k in extra) { const f = r.resolve(extra[k]);"
        + " out.extra[k] = f && Object.assign({}, f, f.graph ? {graph: Object.assign({}, f.graph, {node: f.graph.node.id})} : {}); }\n"
        + "console.log(JSON.stringify(out));\n"
    )
    out = _run_node(tmp_path, source, "routes.js")
    assert out["unresolved"] == []  # every link on every page lands on a page of the file
    assert out["old"]["encoded"] == out["old"]["raw"] == finding_path(finding)
    assert out["old"]["drift"] == out["old"]["drift-dup"] == finding_path(drift)
    assert (
        out["old"]["roadmap"]
        == out["old"]["roadmap-dup"]
        == "/explore/em_legacy_v2.dead_finance_v2"
    )
    assert out["old"]["roadmap-unknown"] == "/overview"
    assert out["old"]["section"] == "/findings?status=all&category=drift"
    assert out["old"]["object"] == "/view/fct_cart_abandonment"
    assert out["old"]["bad-escape"] is None and out["old"]["unknown"] is None
    frame = next(r for r in templates if r.startswith("/graph?"))
    assert out["extra"]["variant"] == {
        "route": frame,
        "graph": {"node": graph_node["id"], "up": 2, "down": 1, "siblings": True},
    }
    assert out["extra"]["browser-encoded"]["graph"]["node"] == graph_node["id"]
    assert out["extra"]["bad-hops"] is None and out["extra"]["unknown-focus"] is None
    assert out["extra"]["search"] == {"route": "/search", "query": "lgcy ord"}
    assert out["extra"]["filter"] == {
        "route": "/findings?status=baselined&category=dead-code",
        "query": "legacy",
    }
    assert out["extra"]["missing"] is None


@node_required
def test_old_fragments_resolve_every_hostile_id_encoded_and_raw(
    hostile: tuple[Workbench, str], tmp_path: Path
) -> None:
    """An id holding a literal escape (`foo%20bar`) decodes to a different string: only the
    raw second try finds it (openHashTarget's rule for links written before encoding)."""
    _, document = hostile
    data = _data(document)
    templates = _templates(document)
    items = data["index"]["items"]
    assert any("%20" in i["id"] for i in items)
    source = (
        _between(ROUTER_JS, "routes")
        + f"const r = makeRoutes({json.dumps(data)}, {json.dumps(list(templates))});\n"
        + f"const items = {json.dumps(items)};\n"
        + "console.log(JSON.stringify(items.map(i => [r.legacy(encodeURIComponent(i.id)), r.legacy(i.id)])));\n"
    )
    got = _run_node(tmp_path, source, "legacy.js")
    # A PDT finding's id is its node id (`pdt:<view>`): the old page anchored the ledger row,
    # the finding, so the finding page wins.
    target = {i["id"]: i["path"] for i in items}
    assert got == [[target[i["id"]], target[i["id"]]] for i in items]
    assert target["pdt:o\"q'<b>"].startswith("/finding/")


@node_required
@pytest.mark.parametrize("fixture", ["enterprise", "hostile"])
def test_graph_href_matches_links_graph_path(
    fixture: str, request: pytest.FixtureRequest, tmp_path: Path
) -> None:
    _, document = request.getfixturevalue(fixture)
    nodes = _data(document)["graph"]["nodes"]
    states = [(u, d, s) for u in (1, 2) for d in (1, 2) for s in (False, True)]
    source = (
        _between(ROUTER_JS, "routes")
        + f"const nodes = {json.dumps(nodes)}, states = {json.dumps(states)};\n"
        + "console.log(JSON.stringify(nodes.map(n => states.map(s => graphHref(n.graph, s[0], s[1], s[2])))));\n"
    )
    got = _run_node(tmp_path, source, "href.js")
    want = [[graph_path(n["id"], u, d, s) for u, d, s in states] for n in nodes]
    assert got == want


@node_required
@pytest.mark.parametrize("fixture", ["enterprise", "hostile"])
def test_graph_js_neighbourhood_matches_python(
    fixture: str, request: pytest.FixtureRequest, tmp_path: Path
) -> None:
    wb, document = request.getfixturevalue(fixture)
    data = _data(document)
    full = _live(wb).graph_data
    cases = [
        (n["id"], up, down, sib, cap)
        for n in data["graph"]["nodes"]
        for up, down, sib, cap in (
            (1, 1, False, NODE_CAP),
            (2, 2, True, NODE_CAP),
            (2, 1, False, 3),
            (1, 2, True, 2),
        )
    ]
    source = (
        _between(GRAPH_JS, "neighbourhood")
        + f"const data = {json.dumps(data['graph'])}, cases = {json.dumps(cases)};\n"
        + "console.log(JSON.stringify(cases.map(c => neighbourhood(data, c[0], c[1], c[2], c[3], c[4]))));\n"
    )
    got = _run_node(tmp_path, source, "hood.js")
    keys = (*EXPORT_NODE_KEYS, "ring", "focus")
    for (focus, up, down, sib, cap), js in zip(cases, got, strict=True):
        py = neighbourhood(full, focus, up=up, down=down, siblings=sib, cap=cap)
        assert py is not None
        expected = {
            **{k: py[k] for k in ("focus", "up", "down", "siblings", "total", "shown")},
            "nodes": [
                {"data": {k: n["data"][k] for k in keys if k != "graph"}} for n in py["nodes"]
            ],
            "edges": [{"data": {k: e["data"][k] for k in EXPORT_EDGE_KEYS}} for e in py["edges"]],
        }
        for n in js["nodes"]:
            n["data"].pop("graph")
        assert js == expected, (focus, up, down, sib, cap)


@node_required
@pytest.mark.parametrize("base", [None, "https://acme.example/strata.html"])
def test_copy_pr_comment_offline_matches_the_server(base: str | None, tmp_path: Path) -> None:
    wb = _workbench(REPO, USAGE, SCHEMA, base_url=base)
    data = export_data(_read_only(wb))
    ids = sorted(wb.findings_by_id)
    selections = [[i] for i in ids] + [ids[:2], ids[3:7], [ids[0], ids[0]], ids, ["not-a-finding"]]
    source = (
        _between(ROUTER_JS, "routes")
        + f"const comments = {json.dumps(data['comments'])}, picks = {json.dumps(selections)};\n"
        + "console.log(JSON.stringify(picks.map(p => prComment(comments, p))));\n"
    )
    got = _run_node(tmp_path, source, "comment.js")
    subject = {"kind": "finding", "id": "", "name": ""}
    for pick, text in zip(selections, got, strict=True):
        records = [dict(r) for i in dict.fromkeys(pick) for r in wb.findings_by_id.get(i, ())]
        # The live list's `c`: GET /api/pr-comment?id=... builds exactly this.
        assert text == (pr_comment(records, subject, base) if records else None), pick


@pytest.mark.parametrize("path", [ROUTER_JS, GRAPH_JS], ids=lambda p: p.name)
def test_export_scripts_have_no_html_parsing_sinks(path: Path) -> None:
    assert _sinks(path.read_text(encoding="utf-8")) == []


@node_required
def test_router_passes_node_check() -> None:
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run([node, "--check", str(ROUTER_JS)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_page_takes_the_title_and_main_and_refuses_a_bare_error(
    enterprise: tuple[Workbench, str],
) -> None:
    wb, _ = enterprise
    app = App(
        wb, frozenset({EXPORT_HOST}), "", Staleness(wb.inputs, wb.fingerprint), read_only=True
    )
    title, main = page(app, "/overview")
    assert title == "Overview" and main.startswith("\n") and "<main>" not in main
    with pytest.raises(ValueError, match="did not render a workbench page"):
        page(_read_only(wb), "/overview")  # another Host: a bare 403, no page


# --- size and speed, measured at scale (spec §6b Q4) ---------------------------------------------

# Measured 2026-11-08 (recorded in the README): large 14.8 MB, very large 35.7 MB; render time
# on an M4 Mac mini 2.8 s / 16.1 s, on the CI runner (ubuntu-latest, Python 3.11) very large
# 48.3 s, about 3x the mini, so large there is about 8.3 s. Bytes are deterministic and capped
# at 1.5x. Time is capped at 1.5x the slowest machine that runs the suite (CI): a page-count
# or per-page regression of the kind that took 20 copies to 325 s still fails by far.
SCALES = {
    "large": (20, 22_200_000, 12.5),
    "very large": (50, 53_600_000, 72.0),
}


@pytest.mark.parametrize("scale", list(SCALES))
def test_export_size_and_render_time_at_scale(scale: str, tmp_path: Path) -> None:
    copies, max_bytes, max_seconds = SCALES[scale]
    repo, usage, schema = generate(tmp_path, copies)
    wb = _workbench(repo, usage, schema)
    started = time.perf_counter()
    document = export(wb)
    seconds = time.perf_counter() - started
    size = len(document.encode("utf-8"))
    assert len(wb.findings_by_id) == 27 * copies  # every copy's findings, none shared
    assert size <= max_bytes, f"{scale}: {size:,} bytes"
    assert seconds <= max_seconds, f"{scale}: {seconds:.1f} s"
