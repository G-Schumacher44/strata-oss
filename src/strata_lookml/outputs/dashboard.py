"""Generate a self-contained HTML observability dashboard from Strata artifacts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from strata_lookml.ir.types import IRGraph, explore_key
from strata_lookml.l1.enrich import analysis_coverage, evidence_facts, view_consumer_map

# Evidence-id namespaces the embedded JS's evidenceSentence() dispatcher must handle —
# one case per entry, or a named deliberate fallback. Mirrored by hand in the JS switch
# (search this file for "case '"); tests/test_l1_synthesis_outputs.py pins the real
# enterprise_mono artifacts against this set so a future namespace can't silently no-op.
KNOWN_EVIDENCE_NAMESPACES = frozenset(
    {
        "dead",
        "explore",
        "view",
        "pdt",
        "field",
        "usage",
        "pdt_build",
        "schema_table",
        "physical_table",
    }
)


# The one source for graph status colors: _build_graph_data stamps these onto nodes/edges
# and build_dashboard_html emits the same dict as CSS custom properties (--n-<key>), which
# the legend and status badges read. A node can never disagree with the legend that
# explains it, because both come from here.
NODE_PALETTE = {
    "explore_active": "#3fbf8f",
    "explore_dead": "#f06b5d",
    "explore_unknown": "#8f9aab",  # usage facts not loaded: activity is unknown, not active
    "view_active": "#6aa5e0",
    "view_orphan": "#7c8696",
    "zombie": "#a98bf5",
    "pdt_unused": "#eaa53f",
    "pdt_used": "#3fbf8f",
    "pdt_unknown": "#8f9aab",
    "physical_table": "#6f7f94",
}
EDGE_PALETTE = {
    "explore→base_view": "#9fb0c6",
    "explore→joined_view": "#6d7c91",
    "view→physical_table": "#55637a",
    "view→pdt": "#eaa53f",
}


def _palette_css() -> str:
    """Both palettes as CSS custom properties for the template's :root block: --n-<status>
    for nodes, --e-<target kind> for edges (e.g. explore→joined_view -> --e-joined-view)."""
    nodes = [f"--n-{key.replace('_', '-')}: {hex_};" for key, hex_ in NODE_PALETTE.items()]
    edges = [
        f"--e-{relation.split('→')[1].replace('_', '-')}: {hex_};"
        for relation, hex_ in EDGE_PALETTE.items()
    ]
    return " ".join(nodes + edges)


def _read_js(filename: str) -> str:
    js_dir = Path(__file__).resolve().parent.parent / "assets" / "js"
    return (js_dir / filename).read_text(encoding="utf-8")


def _embed_json(obj: Any) -> str:
    """json.dumps for embedding inside an inline <script> block. json.dumps leaves `<`
    intact, so a data value containing `</script>` would terminate the surrounding script
    element and hand the rest of the payload to the HTML parser as markup (Codex PR #28
    r6 — the classic script-breakout). `\\u003c` is identical to `<` after JS string
    parsing, so this is a pure serialization change, invisible to every consumer."""
    return json.dumps(obj).replace("<", "\\u003c")


def _build_l1_facts(graph: IRGraph) -> dict[str, Any]:
    """Serializes the raw L1 facts the evidence-sentence panel needs, keyed to match the
    `usage:`/`pdt_build:`/`schema_table:` evidence-id suffixes so the JS looks numbers up
    rather than re-deriving them (the panel-vs-canonical-source drift PR #25's review
    rounds kept catching). Aggregation (content-ref counts, column-count derivation) lives
    in `l1.enrich.evidence_facts()` — this function only reshapes what L1 already computed
    (per outputs/AGENTS.md: outputs serialize, they do not derive)."""
    l1 = graph.metadata.get("l1", {})
    facts = evidence_facts(graph)

    usage = {f"explore:{key}": dict(rec) for key, rec in facts["explore_usage_evidence"].items()}

    pdt_build = {
        view: {
            "build_count": rec["build_count"],
            "bytes_processed": rec["bytes_processed"],
            "estimated_cost_usd": rec["estimated_cost_usd"],
        }
        for view, rec in l1.get("pdt_builds", {}).items()
    }

    return {
        "period": l1.get("period") or {},
        "usage": usage,
        "pdt_build": pdt_build,
        "schema_table": facts["schema_table_facts"],
    }


def build_dashboard_html(artifacts: dict[str, Any], graph: IRGraph) -> str:
    graph_data = _build_graph_data(graph)
    catalog = _embed_json(artifacts.get("catalog", []))
    dead_code = _embed_json(artifacts.get("dead_code_register", []))
    pdt_ledger = _embed_json(artifacts.get("pdt_ledger", []))
    roadmap = _embed_json(artifacts.get("cleanup_roadmap", []))
    schema_drift = _embed_json(artifacts.get("schema_drift", []))
    usage_summary = _embed_json(artifacts.get("usage_summary") or {})
    migration = _embed_json(artifacts.get("migration_impact", []))
    graph_json = _embed_json(graph_data)
    l1_facts = _embed_json(_build_l1_facts(graph))
    coverage_flags = analysis_coverage(graph)
    coverage = _embed_json(coverage_flags)
    data_block = (
        f"const CATALOG       = {catalog};\n"
        f"const DEAD_CODE     = {dead_code};\n"
        f"const PDT_LEDGER    = {pdt_ledger};\n"
        f"const ROADMAP       = {roadmap};\n"
        f"const SCHEMA_DRIFT  = {schema_drift};\n"
        f"const USAGE_SUMMARY = {usage_summary};\n"
        f"const MIGRATION     = {migration};\n"
        f"const GRAPH_DATA    = {graph_json};\n"
        f"const L1_FACTS      = {l1_facts};\n"
        f"const COVERAGE      = {coverage};\n"
    )
    scripts = "\n".join(
        [
            f"<script>{_read_js('cytoscape.min.js')}</script>",
            f"<script>{_read_js('dagre.min.js')}</script>",
            f"<script>{_read_js('cytoscape-dagre.min.js')}</script>",
            f"<script>{_read_js('chart.umd.min.js')}</script>",
        ]
    )
    return (
        _HTML_TEMPLATE.replace("/*__DATA__*/", data_block)
        .replace("/*__SCRIPTS__*/", scripts)
        .replace("/*__PALETTE__*/", _palette_css())
        .replace("/*__USAGE_NOTE_HIDDEN__*/", " hidden" if coverage_flags["usage"] else "")
    )


def _build_graph_data(graph: IRGraph) -> dict[str, Any]:
    l1 = graph.metadata.get("l1", {})
    dead_ids = {r["name"] for r in l1.get("dead_code", [])}
    _eu = l1.get("explore_usage", {})
    usage_map = (
        {k: v["query_count"] for k, v in _eu.items()}
        if isinstance(_eu, dict)
        else {
            explore_key(r["model"], r["explore"]): r["query_count"]
            for r in _eu
            if isinstance(r, dict)
        }
    )
    pdt_records = {r["view"]: r for r in l1.get("pdt_ledger", [])}
    # Dead status needs usage evidence; with none loaded an explore is "unknown", never green.
    usage_loaded = analysis_coverage(graph)["usage"]

    # One edge pass builds every cross-kind lookup the node-detail panel needs — computed
    # once here so the panel never re-derives a fact JS-side that L1 already established
    # (the model-qualified-dead-explore bug from PR #21 was exactly that kind of drift).
    explore_views: dict[str, list[str]] = {}
    view_pdt: dict[str, str] = {}
    table_views: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.relation in {"explore→base_view", "explore→joined_view"} and edge.target.startswith(
            "view:"
        ):
            explore_node = graph.nodes.get(edge.source)
            view_name = edge.target.removeprefix("view:")
            if explore_node and explore_node.kind == "explore":
                explore_views.setdefault(explore_node.id, []).append(view_name)
        elif edge.relation == "view→pdt" and edge.target.startswith("pdt:"):
            view_pdt[edge.source.removeprefix("view:")] = edge.target.removeprefix("pdt:")
        elif edge.relation == "view→physical_table" and edge.target.startswith("physical_table:"):
            table_views.setdefault(edge.target.removeprefix("physical_table:"), []).append(
                edge.source.removeprefix("view:")
            )
        elif edge.relation == "pdt→upstream" and edge.target.startswith("physical_table:"):
            # Derived-table SQL references count too: the resolver records them as
            # pdt→upstream, and strata_impact() maps the PDT back to its view
            # (mcp/tools.py) — the panel mirrors that mapping or it undercounts exactly
            # the references a deletion would break (Codex r5, PR #25).
            pdt_node = graph.nodes.get(edge.source)
            if pdt_node is not None:
                table_views.setdefault(edge.target.removeprefix("physical_table:"), []).append(
                    pdt_node.name
                )
    # Consumers come from L1's ancestry-aware single source — the dashboard must never
    # re-derive them (PR #25 Codex round 2: a local propagation here could disagree with
    # the register/ledger, which use the same map via _explores_using_view).
    view_explores = view_consumer_map(graph)
    table_views = {name: sorted(set(views)) for name, views in table_views.items()}

    def consumers(keys: list[str]) -> list[dict[str, Any]]:
        return [{"key": k, "dead": k in dead_ids} for k in keys]

    # An explore displays as its bare name unless another model has an explore of that name.
    explore_names = Counter(node.name for node in graph.nodes_by_kind("explore"))
    shared_explore_names = {name for name, count in explore_names.items() if count > 1}

    nodes = []
    for node in graph.nodes.values():
        if node.kind not in {"explore", "view", "physical_table", "pdt"}:
            continue
        model = node.attrs.get("model", "")
        # Dead-code register names EXPLORES model-qualified ("em_legacy_v2.dead_finance_v2")
        # but views bare — a bare-name lookup silently missed every dead explore, so they
        # rendered green/KEEP in the graph (caught regenerating the README screenshots on
        # PR #21: dead_finance_v2 showed QUERY COUNT 0 with a KEEP badge).
        is_dead = (
            (explore_key(model, node.name) in dead_ids)
            if node.kind == "explore"
            else (node.name in dead_ids)
        )
        qcount = usage_map.get(explore_key(model, node.name), 0) if node.kind == "explore" else 0
        is_orphan_struct = bool(node.attrs.get("orphan", False))
        orphan = is_orphan_struct or is_dead

        extra: dict[str, Any] = {}
        if node.kind == "explore":
            views_for_explore = explore_views.get(node.id, [])
            extra["pdt_dependencies"] = sorted(
                {view_pdt[v] for v in views_for_explore if v in view_pdt}
            )
            extra["status"] = "dead" if is_dead else "active" if usage_loaded else "unknown"
            color = NODE_PALETTE[
                "explore_dead"
                if is_dead
                else "explore_active"
                if usage_loaded
                else "explore_unknown"
            ]
            shape = "ellipse"
            # Demand reads as size, capped so a heavy explore can't crowd its rank.
            size = max(14, min(28, 14 + qcount // 50))
        elif node.kind == "pdt":
            record = pdt_records.get(node.name)
            status = record["status"] if record else "missing_build_facts"
            extra.update(
                status=status,
                estimated_cost_usd=record["estimated_cost_usd"] if record else 0.0,
                build_count=record["build_count"] if record else 0,
                bytes_processed=record["bytes_processed"] if record else 0,
                used_by_explores=consumers(record["used_by_explores"] if record else []),
            )
            # Zombie (real infra, dead demand) is purple; unused is orange; in-use is
            # green — the three-way vocabulary the legend teaches (see #2 in the slice).
            color = NODE_PALETTE[
                "zombie"
                if status == "zombie"
                else "pdt_unused"
                if status == "unused"
                else "pdt_used"
                if status == "used"
                else "pdt_unknown"  # missing_build_facts — no cost data to render a verdict from
            ]
            shape = "diamond"
            size = 22
        elif node.kind == "view":
            referencing = view_explores.get(node.name, [])
            # Zombie view: structurally referenced (unlike a true orphan) but every
            # referencing explore is itself dead — alive wiring, dead demand.
            is_zombie_view = (
                not is_orphan_struct
                and bool(referencing)
                and all(k in dead_ids for k in referencing)
            )
            view_status = (
                "orphaned" if is_orphan_struct else "zombie_view" if is_zombie_view else "active"
            )
            extra.update(status=view_status, referencing_explores=consumers(referencing))
            color = NODE_PALETTE[
                "view_orphan" if is_orphan_struct else "zombie" if is_zombie_view else "view_active"
            ]
            shape = "round-rectangle"
            size = 16
        else:  # physical_table
            extra["referencing_views"] = table_views.get(node.name, [])
            color = NODE_PALETTE["physical_table"]
            shape = "barrel"
            size = 16

        # One flag the graph's "Needs attention" filter reads, so the filter can't drift from
        # the statuses above: dead/orphaned anything, zombie views, zombie or unused PDTs.
        attention = orphan or extra.get("status") in {"zombie", "unused", "zombie_view"}

        nodes.append(
            {
                "data": {
                    "id": node.id,
                    # `label` stays the bare name: the JS builds `model.label` fact keys from it.
                    "label": node.name,
                    "display_label": explore_key(model, node.name)
                    if node.kind == "explore" and node.name in shared_explore_names
                    else node.name,
                    "kind": node.kind,
                    "source_file": node.source_file,
                    "dead": is_dead,
                    "orphan": orphan,
                    "attention": attention,
                    "query_count": qcount,
                    "model": model,
                    "color": color,
                    "size": size,
                    "shape": shape,
                    **extra,
                }
            }
        )

    edges = []
    seen = set()
    for edge in graph.edges:
        if edge.relation not in {
            "explore→base_view",
            "explore→joined_view",
            "view→physical_table",
            "view→pdt",
        }:
            continue
        edge_key = (edge.source, edge.target, edge.relation)
        if edge_key in seen:
            continue
        seen.add(edge_key)
        if edge.source not in graph.nodes or edge.target not in graph.nodes:
            continue
        src = graph.nodes[edge.source]
        tgt = graph.nodes[edge.target]
        if src.kind not in {"explore", "view", "pdt"} or tgt.kind not in {
            "view",
            "physical_table",
            "pdt",
        }:
            continue

        edges.append(
            {
                "data": {
                    "id": f"{edge.source}__{edge.target}",
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "color": EDGE_PALETTE[edge.relation],
                }
            }
        )

    return {"nodes": nodes, "edges": edges}


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Strata — Repo Health Dashboard</title>
/*__SCRIPTS__*/
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  /* Graph status colors — emitted from NODE_PALETTE (dashboard.py), never hand-copied. */
  /*__PALETTE__*/
  --bg: #121820;
  --surface: #19212b;
  --surface2: #202a36;
  --surface3: #283342;
  --border: #2b3645;
  --line-soft: rgba(43,54,69,.65);
  --text: #e8ecf1;
  --text-2: #b7c0cc;
  --muted: #8794a6;
  --focus: #8cc4ff;
  /* Semantic aliases over the palette, so badges, KPIs and nodes share one vocabulary. */
  --green: var(--n-explore-active);
  --red: var(--n-explore-dead);
  --orange: var(--n-pdt-unused);
  --blue: var(--n-view-active);
  --purple: var(--n-zombie);
  --radius: 12px;
  --radius-sm: 6px;
  --sans: ui-sans-serif, -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
  --step--1: 12px; --step-0: 14px; --step-1: 16px; --step-2: 20px; --step-3: 28px; --step-4: 40px;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px; --space-5: 24px; --space-6: 32px; --space-7: 48px;
}
html { scroll-behavior: smooth; scroll-padding-top: 64px; }
@media (prefers-reduced-motion: reduce) { html { scroll-behavior: auto; } }
body { background: var(--bg); color: var(--text); font-family: var(--sans); font-size: var(--step-0); line-height: 1.55; -webkit-font-smoothing: antialiased; font-variant-numeric: tabular-nums; }
a { color: var(--focus); text-decoration: none; }
code, .mono { font-family: var(--mono); }
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; border-radius: 4px; }

/* Layout */
.page { max-width: 1360px; margin: 0 auto; padding: 0 var(--space-5) var(--space-7); }
.topbar { position: sticky; top: 0; z-index: 20; background: rgba(18,24,32,.92); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); border-bottom: 1px solid var(--border); }
.topbar-inner { max-width: 1360px; margin: 0 auto; padding: 0 var(--space-5); display: flex; align-items: center; gap: var(--space-5); height: 52px; }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: var(--step-1); letter-spacing: -0.01em; color: var(--text); white-space: nowrap; }
.brand-mark { display: grid; gap: 2px; width: 18px; }
.brand-mark span { display: block; height: 4px; border-radius: 2px; }
.brand-mark span:nth-child(1) { background: var(--n-explore-active); width: 100%; }
.brand-mark span:nth-child(2) { background: var(--n-view-active); width: 78%; }
.brand-mark span:nth-child(3) { background: var(--n-physical-table); width: 56%; }
.nav { display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; margin-left: auto; }
.nav::-webkit-scrollbar { display: none; }
.nav a { color: var(--muted); font-size: 13px; padding: 6px 10px; border-radius: var(--radius-sm); white-space: nowrap; }
.nav a:hover { color: var(--text); background: var(--surface2); }

.hero { padding: var(--space-7) 0 var(--space-5); display: grid; gap: var(--space-3); }
.hero h1 { font-size: var(--step-3); line-height: 1.2; font-weight: 650; letter-spacing: -0.02em; max-width: 30ch; }
.hero-lede { color: var(--text-2); font-size: var(--step-1); max-width: 68ch; }
.hero-meta { color: var(--muted); font-size: var(--step--1); }

.badge { display: inline-flex; align-items: center; gap: 5px; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 600; letter-spacing: 0.01em; white-space: nowrap; }
.badge-green { background: color-mix(in srgb, var(--green) 16%, transparent); color: var(--green); }
.badge-red { background: color-mix(in srgb, var(--red) 16%, transparent); color: var(--red); }
.badge-orange { background: color-mix(in srgb, var(--orange) 16%, transparent); color: var(--orange); }
.badge-blue { background: color-mix(in srgb, var(--blue) 16%, transparent); color: var(--blue); }
.badge-gray { background: rgba(135,148,166,.14); color: var(--muted); }

/* KPI row — ordered by what needs attention first; each card jumps to its section. */
.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-6); }
.kpi-card { position: relative; display: block; color: inherit; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: var(--space-4) var(--space-4) var(--space-4) calc(var(--space-4) + 4px); overflow: hidden; transition: border-color .15s, background .15s; }
.kpi-card::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--kpi-accent, var(--border)); }
a.kpi-card:hover { border-color: var(--kpi-accent, var(--muted)); background: var(--surface2); }
.kpi-card .label { font-size: 13px; color: var(--text-2); margin-bottom: var(--space-2); }
.kpi-card .value { font-size: var(--step-3); font-weight: 700; line-height: 1.05; letter-spacing: -0.02em; color: var(--kpi-accent, var(--text)); }
.kpi-card .sub { font-size: var(--step--1); color: var(--muted); margin-top: var(--space-2); }
.kpi-card.warn { --kpi-accent: var(--red); }
.kpi-card.caution { --kpi-accent: var(--orange); }
.kpi-card.ok { --kpi-accent: var(--green); }
.kpi-card.info { --kpi-accent: var(--blue); }

/* Section cards */
.section { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: var(--space-5); overflow: hidden; }
.section-header { display: flex; align-items: baseline; flex-wrap: wrap; gap: var(--space-2) var(--space-3); padding: var(--space-4) var(--space-5); border-bottom: 1px solid var(--border); }
.section-header h2 { font-size: var(--step-1); font-weight: 650; letter-spacing: -0.01em; }
.section-header .hint { font-size: 13px; color: var(--muted); }
.section-header .count { font-size: 13px; color: var(--muted); margin-left: auto; }
.section-body { padding: var(--space-5); }

/* Graph */
.graph-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2); padding: var(--space-3) var(--space-5); border-bottom: 1px solid var(--border); background: var(--surface); }
.graph-search { position: relative; flex: 1 1 240px; max-width: 360px; }
.graph-search input { width: 100%; height: 34px; padding: 0 12px 0 32px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg); color: var(--text); font: inherit; font-size: 13px; }
.graph-search input::placeholder { color: var(--muted); }
.graph-search input:focus { outline: none; border-color: var(--focus); box-shadow: 0 0 0 3px rgba(140,196,255,.18); }
.graph-search svg { position: absolute; left: 10px; top: 9px; width: 16px; height: 16px; stroke: var(--muted); fill: none; stroke-width: 2; }
.chip-group { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 11px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text-2); font: inherit; font-size: 12.5px; cursor: pointer; }
.chip:hover { border-color: var(--muted); color: var(--text); }
.chip[aria-pressed="false"] { color: var(--muted); opacity: .55; text-decoration: line-through; text-decoration-color: rgba(135,148,166,.6); }
.chip.toggle[aria-pressed="false"] { opacity: 1; text-decoration: none; }
.chip.toggle[aria-pressed="true"] { background: color-mix(in srgb, var(--red) 16%, transparent); border-color: color-mix(in srgb, var(--red) 55%, transparent); color: var(--text); }
.chip .glyph { width: 10px; height: 10px; flex-shrink: 0; }
.graph-count { margin-left: auto; font-size: 12.5px; color: var(--muted); white-space: nowrap; }

#cy-container { display: grid; grid-template-columns: minmax(0, 1fr) 320px; min-height: 0; }
.cy-wrap { position: relative; min-width: 0; border-right: 1px solid var(--border); }
#cy { width: 100%; height: min(76vh, 760px); min-height: 460px; background: radial-gradient(ellipse at 50% 0%, #17202b 0%, var(--bg) 70%); }
.cy-lanes { position: absolute; inset: 0 0 auto 0; height: 0; pointer-events: none; z-index: 3; }
.cy-lane { position: absolute; top: 12px; transform: translateX(-50%); font-size: 11.5px; color: var(--muted); background: rgba(18,24,32,.85); border: 1px solid var(--border); padding: 2px 10px; border-radius: 999px; white-space: nowrap; }
.cy-controls { position: absolute; bottom: 14px; right: 14px; display: flex; flex-direction: column; gap: 4px; z-index: 5; background: rgba(25,33,43,.92); border: 1px solid var(--border); border-radius: 10px; padding: 4px; }
.cy-btn { width: 32px; height: 32px; border-radius: 7px; border: none; background: transparent; color: var(--text-2); font-size: 16px; line-height: 1; cursor: pointer; display: grid; place-items: center; }
.cy-btn svg { width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.cy-btn:hover:not(:disabled) { background: var(--surface3); color: var(--text); }
.cy-btn:disabled { opacity: .35; cursor: default; }
.cy-hint { position: absolute; left: 14px; bottom: 14px; z-index: 4; font-size: 12px; color: var(--muted); background: rgba(18,24,32,.8); padding: 4px 10px; border-radius: 999px; border: 1px solid var(--border); pointer-events: none; }
.cy-tip { position: absolute; z-index: 6; pointer-events: none; background: var(--surface3); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 6px 10px; font-size: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.35); max-width: 340px; display: none; }
.cy-tip .tip-name { font-family: var(--mono); font-weight: 600; word-break: break-all; }
.cy-tip .tip-meta { color: var(--muted); margin-top: 2px; }
#detail-panel { background: var(--surface); padding: var(--space-4) var(--space-5); overflow-y: auto; max-height: min(76vh, 760px); }
#detail-panel h3 { font-size: 13px; font-weight: 600; margin-bottom: var(--space-3); color: var(--muted); }
.detail-row { margin-bottom: var(--space-3); }
.detail-row .key { font-size: 12px; color: var(--muted); margin-bottom: 2px; }
.detail-row .val { font-size: 13px; word-break: break-word; }
.detail-empty { color: var(--muted); font-size: 13px; padding: var(--space-5) 0; line-height: 1.6; }
.detail-empty strong { color: var(--text-2); font-weight: 600; display: block; margin-bottom: 4px; }
.consumer-row { font-size: 12px; font-family: var(--mono); margin-bottom: 2px; }
.nbr-list { display: flex; flex-direction: column; gap: 2px; }
.nbr-btn { display: flex; align-items: center; gap: 8px; width: 100%; text-align: left; border: 1px solid transparent; background: none; color: var(--text-2); font-family: var(--mono); font-size: 12px; padding: 3px 6px; border-radius: 6px; cursor: pointer; }
.nbr-btn:hover { background: var(--surface2); border-color: var(--border); color: var(--text); }
.nbr-btn .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.nbr-btn .nbr-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nbr-btn .nbr-kind { margin-left: auto; padding-left: 8px; font-family: var(--sans); font-size: 11px; color: var(--muted); flex-shrink: 0; }
.start-here { margin-top: var(--space-5); padding-top: var(--space-4); border-top: 1px solid var(--border); }
.start-here .key { color: var(--text-2); font-weight: 600; }

.legend { display: flex; flex-wrap: wrap; gap: var(--space-2) var(--space-6); padding: var(--space-4) var(--space-5); border-top: 1px solid var(--border); }
.legend-group { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; }
.legend-group .lg-title { font-size: 12px; color: var(--text-2); font-weight: 600; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); }
.legend-item[hidden] { display: none; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.legend-rect { width: 14px; height: 9px; border-radius: 3px; flex-shrink: 0; }
.legend-diamond { width: 9px; height: 9px; transform: rotate(45deg); border-radius: 1px; flex-shrink: 0; margin: 0 1px; }
.legend-barrel { width: 12px; height: 10px; border-radius: 3px / 5px; flex-shrink: 0; }
.legend-line { width: 22px; height: 0; border-top: 2px solid; flex-shrink: 0; }

/* Tables */
.table-wrap { overflow: auto; max-height: 560px; border: 1px solid var(--border); border-radius: 10px; }
table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; }
th { position: sticky; top: 0; z-index: 1; text-align: left; font-size: 12px; color: var(--text-2); padding: 10px 12px; background: var(--surface2); border-bottom: 1px solid var(--border); font-weight: 600; white-space: nowrap; }
th.sortable { cursor: pointer; user-select: none; }
th.sortable:hover { color: var(--text); }
th.sortable::after { content: "↕"; margin-left: 6px; color: var(--muted); opacity: .5; font-size: 11px; }
th[aria-sort="ascending"]::after { content: "↑"; opacity: 1; color: var(--focus); }
th[aria-sort="descending"]::after { content: "↓"; opacity: 1; color: var(--focus); }
td { padding: 11px 12px; border-bottom: 1px solid var(--line-soft); vertical-align: top; }
tbody tr:last-child td { border-bottom: none; }
tbody tr:hover td { background: rgba(255,255,255,.018); }
tr.dead-row td:first-child { box-shadow: inset 3px 0 0 color-mix(in srgb, var(--red) 55%, transparent); }
td.num, th.num { text-align: right; white-space: nowrap; }
.file-tag { font-size: 12px; color: var(--muted); font-family: var(--mono); word-break: break-all; }
.reason-text { color: var(--muted); font-size: 12px; margin-top: 3px; }
.pill { display: inline-block; padding: 1px 8px; border-radius: 999px; font-size: 11px; font-weight: 500; margin: 2px 2px 0 0; background: rgba(135,148,166,.12); color: var(--text-2); font-family: var(--mono); word-break: break-all; }
a.ev-chip { cursor: pointer; border: 1px solid transparent; text-decoration: none; }
a.pill-link:hover { background: color-mix(in srgb, var(--focus) 18%, transparent); color: var(--focus); border-color: color-mix(in srgb, var(--focus) 60%, transparent); }
a.pill-info:hover { background: rgba(135,148,166,.25); color: var(--text); border-color: var(--muted); }
a.row-primary-link { display: inline; padding: 0; border: none; background: none; color: var(--text); font: inherit; margin: 0; overflow-wrap: anywhere; }
td.mono { min-width: 220px; }
a.row-primary-link:hover { color: var(--focus); background: none; text-decoration: underline; text-underline-offset: 3px; }
.copy-link-btn { border: none; background: none; color: var(--muted); cursor: pointer; font-size: 11px; margin-left: 6px; padding: 0; vertical-align: middle; opacity: .55; }
tr:hover .copy-link-btn, li:hover .copy-link-btn, .copy-link-btn:focus-visible { opacity: 1; }
.copy-link-btn:hover { color: var(--focus); }
.evidence-sentence { display: block; font-size: 12.5px; line-height: 1.55; color: var(--text); background: color-mix(in srgb, var(--focus) 8%, var(--surface2)); border: 1px solid var(--border); border-left: 3px solid var(--focus); border-radius: 6px; padding: 8px 10px; margin: 6px 0 8px; max-width: 560px; font-family: var(--sans); font-weight: 400; word-break: normal; }
.evidence-details summary { cursor: pointer; font-size: 12px; color: var(--muted); }
.evidence-details summary:hover { color: var(--focus); }
.evidence-list { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 2px; }

/* PDT section */
.pdt-layout { display: grid; gap: var(--space-5); }
.pdt-layout > * { min-width: 0; }
.chart-wrap { position: relative; height: 180px; }
.kill-badge, .zombie-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px; border-radius: 999px; font-size: 11.5px; font-weight: 600; white-space: nowrap; }
.kill-badge { background: color-mix(in srgb, var(--orange) 18%, transparent); color: var(--orange); }
.zombie-badge { background: color-mix(in srgb, var(--purple) 18%, transparent); color: var(--purple); }

/* Roadmap — a ranked list (sorted by savings), so the numbering carries meaning. */
.roadmap-list { list-style: none; }
.roadmap-item { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--line-soft); }
.roadmap-item:last-child { border-bottom: none; }
.roadmap-num { width: 26px; height: 26px; border-radius: 50%; background: var(--surface2); border: 1px solid var(--border); display: flex; align-items: center; justify-content: center; font-size: 11.5px; font-weight: 700; color: var(--text-2); flex-shrink: 0; }
.roadmap-body { flex: 1; min-width: 0; }
.roadmap-target { font-weight: 600; font-size: 13px; font-family: var(--mono); }
.roadmap-meta { font-size: 12px; color: var(--muted); margin-top: 2px; }

/* Accordion */
.accordion-item { border-bottom: 1px solid var(--line-soft); }
.accordion-item:last-child { border-bottom: none; }
.accordion-trigger { width: 100%; text-align: left; background: none; border: none; color: var(--text); font-size: 13px; padding: 12px 0; cursor: pointer; display: flex; align-items: center; gap: 10px; font-family: inherit; }
.accordion-trigger:hover { color: var(--focus); }
.accordion-trigger .arrow { transition: transform .2s; font-size: 10px; color: var(--muted); }
.accordion-trigger.open .arrow { transform: rotate(90deg); }
.accordion-trigger > span:nth-child(2) { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0; }
.accordion-trigger > span:last-child { flex-shrink: 0; }
.accordion-content { display: none; padding: 0 0 14px 22px; }
.accordion-content.open { display: block; }
.impact-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-3); }
.impact-group label { font-size: 12px; color: var(--text-2); display: block; margin-bottom: 6px; font-weight: 600; }
.impact-group .items { display: flex; flex-direction: column; gap: 3px; align-items: flex-start; }
.impact-tag { font-size: 11.5px; font-family: var(--mono); color: var(--text); background: var(--surface2); padding: 2px 7px; border-radius: 4px; display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Empty state */
.empty { text-align: center; padding: var(--space-6) var(--space-4); color: var(--muted); font-size: 13px; }
.empty .icon { font-size: 22px; margin-bottom: 6px; color: var(--green); }
.empty.skipped { color: var(--text-2); border: 1px dashed var(--border); border-radius: 10px; }
.kpi-card.skipped { --kpi-accent: var(--muted); }
.kpi-card.skipped .value { font-size: var(--step-2); color: var(--muted); }

/* Tooltip */
.tooltip-def { border-bottom: 1px dashed var(--muted); cursor: help; }

@media (max-width: 960px) {
  #cy-container { grid-template-columns: 1fr; }
  .cy-wrap { border-right: none; border-bottom: 1px solid var(--border); }
  #cy { height: 62vh; min-height: 380px; }
  #detail-panel { max-height: none; }
  .impact-grid { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .page { padding: 0 var(--space-4) var(--space-6); }
  .topbar-inner { padding: 0 var(--space-4); gap: var(--space-3); }
  .hero { padding: var(--space-6) 0 var(--space-4); }
  .hero h1 { font-size: 23px; }
  .hero-lede { font-size: var(--step-0); }
  .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
  .kpi-card { padding: var(--space-3) var(--space-3) var(--space-3) calc(var(--space-3) + 4px); }
  .kpi-card .value { font-size: 22px; }
  .section-header, .section-body, .graph-toolbar, .legend { padding-left: var(--space-4); padding-right: var(--space-4); }
  .graph-search { max-width: none; flex-basis: 100%; }
  .graph-count { margin-left: 0; }
  .cy-hint { display: none; }
  .table-wrap table { min-width: 820px; }
}
</style>
</head>
<body>
<div class="topbar">
  <div class="topbar-inner">
    <div class="brand"><span class="brand-mark" aria-hidden="true"><span></span><span></span><span></span></span>Strata</div>
    <nav class="nav" aria-label="Sections">
      <a href="#graph">Graph</a>
      <a href="#dead-code">Dead code</a>
      <a href="#pdt-cost">PDT cost</a>
      <a href="#roadmap">Roadmap</a>
      <a href="#drift">Schema drift</a>
      <a href="#migration">Migration</a>
    </nav>
  </div>
</div>
<div class="page">

<header class="hero">
  <h1 id="hero-headline">LookML repo health</h1>
  <p class="hero-lede" id="hero-lede">Deterministic analysis of your LookML: what is unused, what it costs, and what breaks if a table changes.</p>
  <div class="hero-meta" id="period-tag"></div>
</header>

<!-- KPI Row -->
<div class="kpi-row" id="kpi-row"></div>

<!-- Dependency Graph -->
<section class="section" id="graph">
  <div class="section-header">
    <h2>Dependency graph</h2>
    <span class="hint">How explores reach views, PDTs and warehouse tables. Hover to trace a path, click to inspect.</span>
  </div>
  <div class="graph-toolbar">
    <label class="graph-search">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>
      <input type="search" id="cy-search" placeholder="Find an explore, view or table" aria-label="Find a node by name" autocomplete="off" spellcheck="false">
    </label>
    <div class="chip-group" role="group" aria-label="Show node types">
      <button type="button" class="chip" data-kind="explore" aria-pressed="true"><svg class="glyph" viewBox="0 0 10 10"><circle cx="5" cy="5" r="5" fill="var(--n-explore-active)"></circle></svg>Explores</button>
      <button type="button" class="chip" data-kind="view" aria-pressed="true"><svg class="glyph" viewBox="0 0 10 10"><rect x="0" y="2" width="10" height="6" rx="2" fill="var(--n-view-active)"></rect></svg>Views</button>
      <button type="button" class="chip" data-kind="pdt" aria-pressed="true"><svg class="glyph" viewBox="0 0 10 10"><path d="M5 0L10 5L5 10L0 5Z" fill="var(--n-pdt-unused)"></path></svg>PDTs</button>
      <button type="button" class="chip" data-kind="physical_table" aria-pressed="true"><svg class="glyph" viewBox="0 0 10 10"><rect x="0" y="1" width="10" height="8" rx="3" fill="var(--n-physical-table)"></rect></svg>Tables</button>
    </div>
    <button type="button" class="chip toggle" id="cy-attention" aria-pressed="false"><svg class="glyph" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="none" stroke="var(--n-explore-dead)" stroke-width="2"></circle></svg>Needs attention</button>
    <span class="graph-count" id="cy-count" aria-live="polite"></span>
  </div>
  <div id="cy-container">
    <div class="cy-wrap">
      <div id="cy" role="img" aria-label="Dependency graph of explores, views, PDTs and physical tables"></div>
      <div class="cy-lanes" id="cy-lanes" aria-hidden="true"></div>
      <div class="cy-tip" id="cy-tip" role="tooltip"></div>
      <div class="cy-hint" id="cy-hint">Pinch or ⌘-scroll to zoom, drag to pan</div>
      <div class="cy-controls">
        <button type="button" class="cy-btn" id="cy-zoom-in" title="Zoom in" aria-label="Zoom in"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"></path></svg></button>
        <button type="button" class="cy-btn" id="cy-zoom-out" title="Zoom out" aria-label="Zoom out"><svg viewBox="0 0 24 24"><path d="M5 12h14"></path></svg></button>
        <button type="button" class="cy-btn" id="cy-focus" title="Zoom to selection" aria-label="Zoom to selection" disabled><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"></circle><path d="M12 2v3M12 19v3M2 12h3M19 12h3"></path></svg></button>
        <button type="button" class="cy-btn" id="cy-fit" title="Fit to view" aria-label="Fit to view"><svg viewBox="0 0 24 24"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"></path></svg></button>
        <button type="button" class="cy-btn" id="cy-reset" title="Clear filters and selection" aria-label="Clear filters and selection"><svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7"></path><path d="M3 4v5h5"></path></svg></button>
      </div>
    </div>
    <div id="detail-panel">
      <h3>Details</h3>
      <div id="detail-content" class="detail-empty"><strong>Nothing selected</strong>Click a node to see its status, cost and what depends on it. Evidence chips in the tables below also jump here.</div>
    </div>
  </div>
  <div class="legend" id="graph-legend">
    <div class="legend-group"><span class="lg-title">Explores</span>
      <div class="legend-item"><div class="legend-dot" style="background:var(--n-explore-active)"></div> Active explore</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--n-explore-dead)"></div> Dead explore</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--n-explore-unknown)"></div> Unknown (no usage facts)</div>
      <div class="legend-item" id="legend-usage-note"/*__USAGE_NOTE_HIDDEN__*/>Usage facts not loaded &mdash; explore activity unknown</div>
    </div>
    <div class="legend-group"><span class="lg-title">Views</span>
      <div class="legend-item"><div class="legend-rect" style="background:var(--n-view-active)"></div> View</div>
      <div class="legend-item"><div class="legend-rect" style="background:var(--n-view-orphan)"></div> Orphaned view</div>
      <div class="legend-item"><div class="legend-rect" style="background:var(--n-zombie)"></div> Zombie view</div>
    </div>
    <div class="legend-group"><span class="lg-title">PDTs</span>
      <div class="legend-item"><div class="legend-diamond" style="background:var(--n-pdt-used)"></div> PDT (in use)</div>
      <div class="legend-item"><div class="legend-diamond" style="background:var(--n-pdt-unused)"></div> PDT (unused)</div>
      <div class="legend-item"><div class="legend-diamond" style="background:var(--n-zombie)"></div> Zombie PDT</div>
      <div class="legend-item"><div class="legend-diamond" style="background:var(--n-pdt-unknown)"></div> No build data</div>
    </div>
    <div class="legend-group"><span class="lg-title">Warehouse</span>
      <div class="legend-item"><div class="legend-barrel" style="background:var(--n-physical-table)"></div> Physical table</div>
    </div>
    <div class="legend-group"><span class="lg-title">Edges</span>
      <div class="legend-item"><div class="legend-line" style="border-color:var(--e-base-view)"></div> Base view</div>
      <div class="legend-item"><div class="legend-line" style="border-color:var(--e-joined-view);border-top-style:dashed"></div> Joined view</div>
      <div class="legend-item"><div class="legend-line" style="border-color:var(--e-physical-table);border-top-style:dotted"></div> Reads table</div>
      <div class="legend-item"><div class="legend-line" style="border-color:var(--e-pdt)"></div> Builds PDT</div>
    </div>
  </div>
</section>

<!-- Dead Code -->
<section class="section" id="dead-code">
  <div class="section-header">
    <h2>Dead code register</h2>
    <span class="hint">Explores and views with no structural or usage reason to exist.</span>
    <span class="count" id="dead-count"></span>
  </div>
  <div class="section-body" id="dead-body"></div>
</section>

<!-- PDT Ledger -->
<section class="section" id="pdt-cost">
  <div class="section-header">
    <h2>PDT cost ledger</h2>
    <span class="hint"><span class="tooltip-def" title="Persistent Derived Table — a precomputed query stored in your warehouse that rebuilds on a schedule">PDT</span> = Persistent Derived Table. Spend on PDTs nothing live reads is money to reclaim.</span>
  </div>
  <div class="section-body" id="pdt-body"></div>
</section>

<!-- Cleanup Roadmap -->
<section class="section" id="roadmap">
  <div class="section-header">
    <h2>Cleanup roadmap</h2>
    <span class="hint">Highest savings first.</span>
    <span class="count" id="roadmap-count"></span>
  </div>
  <div class="section-body" id="roadmap-body"></div>
</section>

<!-- Schema Drift -->
<section class="section" id="drift">
  <div class="section-header">
    <h2>Schema drift</h2>
    <span class="hint">LookML that references tables or columns the warehouse no longer has.</span>
    <span class="count" id="drift-count"></span>
  </div>
  <div class="section-body" id="drift-body"></div>
</section>

<!-- Migration Impact -->
<section class="section" id="migration">
  <div class="section-header">
    <h2>Migration impact</h2>
    <span class="hint">What breaks if a physical table changes?</span>
  </div>
  <div class="section-body" id="migration-body"></div>
</section>

</div><!-- .page -->

<script>
/*__DATA__*/

// ── Period tag ───────────────────────────────────────────────────────────────
(function() {
  const p = USAGE_SUMMARY && USAGE_SUMMARY.period;
  const tag = document.getElementById('period-tag');
  if (tag && p) {
    tag.textContent = 'Usage window ' + p.start + ' to ' + p.end + ' (' + p.days + ' days). Deterministic analysis, no LLM calls.';
  } else if (tag) {
    tag.textContent = 'No usage window: pass a usage fixture or --looker-url to include query counts.';
  }
})();

// ── Helpers ──────────────────────────────────────────────────────────────────
function el(tag, cls) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  return e;
}
function fmt_bytes(b) {
  if (b >= 1e12) return (b/1e12).toFixed(1) + ' TB';
  if (b >= 1e9)  return (b/1e9).toFixed(1) + ' GB';
  if (b >= 1e6)  return (b/1e6).toFixed(1) + ' MB';
  return b + ' B';
}
function fmt_usd(v) { return '$' + v.toFixed(2); }
// Whole-dollar, grouped ("$63,750") for headline copy. Deliberately NOT an innerHTML-safe
// wrapper like fmt_usd: every caller passes its result through escapeHtml() or textContent.
function fmt_money(v) { return '$' + Math.round(Number(v) || 0).toLocaleString('en-US'); }
function plural(n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); }
function wrapTable(tbl) {
  const w = el('div', 'table-wrap');
  w.appendChild(tbl);
  return w;
}
// Click-to-sort on every <th> not marked data-sort="none". Numeric columns (data-sort="num")
// sort on the cell's data-sort-value (the raw number the cell formats), text columns on the
// cell text. Rows are moved, never rebuilt, so ids, chips and open evidence panels survive.
function makeSortable(tbl) {
  const ths = Array.from(tbl.tHead.rows[0].cells);
  ths.forEach((th, idx) => {
    if (th.dataset.sort === 'none') return;
    th.classList.add('sortable');
    th.tabIndex = 0;
    if (!th.hasAttribute('aria-sort')) th.setAttribute('aria-sort', 'none');
    const numeric = th.dataset.sort === 'num';
    const keyOf = row => {
      const cell = row.cells[idx];
      if (!cell) return numeric ? 0 : '';
      const raw = cell.dataset.sortValue != null ? cell.dataset.sortValue : cell.textContent.trim();
      return numeric ? (Number(raw) || 0) : raw.toLowerCase();
    };
    const sortBy = () => {
      const dir = th.getAttribute('aria-sort') === 'descending' ? 'ascending' : 'descending';
      ths.forEach(h => { if (h.classList.contains('sortable')) h.setAttribute('aria-sort', 'none'); });
      th.setAttribute('aria-sort', dir);
      const tbody = tbl.tBodies[0];
      const rows = Array.from(tbody.rows);
      rows.sort((a, b) => {
        const x = keyOf(a), y = keyOf(b);
        const c = numeric ? x - y : String(x).localeCompare(String(y));
        return dir === 'ascending' ? c : -c;
      });
      rows.forEach(r => tbody.appendChild(r));
    };
    th.addEventListener('click', sortBy);
    th.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sortBy(); }
    });
  });
}
function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// ── Evidence linking ────────────────────────────────────────────────────────
// Resolves an evidence id to a graph node id when one exists, so Dead Code Register
// pills and Roadmap evidence links can jump into the graph instead of sitting inert.
const GRAPH_NODE_IDS = new Set((GRAPH_DATA && GRAPH_DATA.nodes || []).map(n => n.data.id));
// Prototype-free: a node or table literally named 'constructor'/'toString'/'__proto__' must
// not resolve to an inherited member, and must not poison the map on assignment either.
const NODE_BY_ID = Object.create(null);
(GRAPH_DATA && GRAPH_DATA.nodes || []).forEach(n => { NODE_BY_ID[n.data.id] = n.data; });

function exploreNodeIdFromKey(key) {
  // "MODEL.NAME" (dead-code/usage-fact key convention) -> "explore:MODEL:NAME" (graph
  // node id convention) — same identity, different separator.
  const dot = key.indexOf('.');
  return dot > -1 ? `explore:${key.slice(0, dot)}:${key.slice(dot + 1)}` : null;
}
function resolveEvidenceNodeId(evId) {
  if (!evId) return null;
  if (GRAPH_NODE_IDS.has(evId)) return evId;
  const mExplore = /^dead:explore:(.+)$/.exec(evId);
  if (mExplore) {
    const candidate = exploreNodeIdFromKey(mExplore[1]);
    if (candidate && GRAPH_NODE_IDS.has(candidate)) return candidate;
  }
  const mView = /^dead:view:(.+)$/.exec(evId);
  if (mView) {
    const candidate = `view:${mView[1]}`;
    if (GRAPH_NODE_IDS.has(candidate)) return candidate;
  }
  return null;
}

// ── Evidence sentences ──────────────────────────────────────────────────────
// Renders the raw L1_FACTS/GRAPH_DATA a chip's evidence id names in analyst language —
// every fact here is a Python-computed number formatted for display, never re-derived.
// JSON.parse produces objects that inherit from Object.prototype, so a bare key like
// 'constructor' or 'toString' would resolve to an inherited member and make a missing
// table read as present. Every L1 fact lookup goes through here.
function ownFact(map, key) {
  return (map && Object.prototype.hasOwnProperty.call(map, key)) ? map[key] : undefined;
}
// Deterministic unique DOM anchor. Data-derived ids are NOT guaranteed unique: a roadmap
// can act twice on one artifact, and two views in different files can produce the same
// SchemaDriftRecord id (same table+column+field). A duplicate id makes every copy-link past
// the first resolve to the wrong row, silently. First occurrence keeps the bare id so links
// already shared stay valid; each later collision gets ':2', ':3', ... in render order.
const ANCHOR_SEEN = Object.create(null);
function uniqueAnchor(base) {
  const n = (ANCHOR_SEEN[base] || 0) + 1;
  ANCHOR_SEEN[base] = n;
  return n > 1 ? base + ':' + n : base;
}
function periodPhrase() {
  const p = L1_FACTS.period || {};
  if (!p.start || !p.end) return 'an unknown window';
  const days = p.days != null ? `${p.days}-day ` : '';
  return `the last ${days}window (${p.start} \u2192 ${p.end})`;
}
function exploreUsageSentence(modelDotName, sourceFile) {
  const fact = ownFact(L1_FACTS.usage, 'explore:' + modelDotName);
  let s;
  if (fact && fact.no_usage_row) {
    const c = fact.content_reference_count || 0;
    s = `no usage row recorded in ${periodPhrase()} (0 queries) \u00b7 ${c} content reference${c !== 1 ? 's' : ''} in the window`;
  } else if (fact) {
    const q = fact.query_count || 0;
    const c = fact.content_reference_count || 0;
    s = `queried ${q} time${q !== 1 ? 's' : ''} in ${periodPhrase()} \u00b7 ${c} content reference${c !== 1 ? 's' : ''} in the window`;
  } else {
    s = `no usage row was provided for '${modelDotName}' in the L1 facts`;
  }
  if (sourceFile) s += ` \u00b7 exists in resolved IR at '${sourceFile}'`;
  return s + '.';
}
function viewSentence(node) {
  const refs = node.referencing_explores || [];
  let s;
  if (node.status === 'orphaned') {
    s = 'no explore references this view (structural orphan)';
  } else if (node.status === 'zombie_view') {
    s = `referenced by ${refs.length} explore${refs.length !== 1 ? 's' : ''}, all currently dead`;
  } else {
    s = `referenced by ${refs.length} explore${refs.length !== 1 ? 's' : ''}`;
  }
  if (node.source_file) s += ` \u00b7 exists in resolved IR at '${node.source_file}'`;
  return s + '.';
}
function pdtCostSentence(buildCount, bytesProcessed, costUsd, usedBy, sourceFile) {
  let s = `built ${buildCount || 0} time${buildCount !== 1 ? 's' : ''}, processing ${fmt_bytes(Number(bytesProcessed || 0))} \u00b7 ${fmt_usd(costUsd || 0)} estimated over ${periodPhrase()}`;
  if (usedBy && usedBy.length) {
    const deadCount = usedBy.filter(c => c.dead).length;
    s += ` \u00b7 used by ${usedBy.length} explore${usedBy.length !== 1 ? 's' : ''}`;
    if (deadCount) s += ` (${deadCount} dead)`;
  } else {
    s += ' \u00b7 no consumers recorded';
  }
  if (sourceFile) s += ` \u00b7 exists in resolved IR at '${sourceFile}'`;
  return s + '.';
}
function evidenceSentence(evId) {
  if (!evId) return 'No evidence id provided.';
  const namespace = evId.split(':')[0];
  switch (namespace) {
    case 'dead': {
      const nodeId = resolveEvidenceNodeId(evId);
      const node = nodeId ? NODE_BY_ID[nodeId] : null;
      if (node && node.kind === 'explore') return exploreUsageSentence(`${node.model}.${node.label}`, node.source_file);
      if (node && node.kind === 'view') return viewSentence(node);
      return `No graph node found for evidence id '${evId}'.`;
    }
    case 'explore': {
      const node = NODE_BY_ID[evId];
      return node
        ? exploreUsageSentence(`${node.model}.${node.label}`, node.source_file)
        : `No graph node found for evidence id '${evId}'.`;
    }
    case 'view': {
      const node = NODE_BY_ID[evId];
      return node ? viewSentence(node) : `No graph node found for evidence id '${evId}'.`;
    }
    case 'pdt': {
      const node = NODE_BY_ID[evId];
      if (!node) return `No graph node found for evidence id '${evId}'.`;
      if (node.status === 'missing_build_facts') {
        return `no PDT build facts were provided for '${node.label}' — cost and build count are unknown` +
          (node.source_file ? ` · exists in resolved IR at '${node.source_file}'` : '') + '.';
      }
      return pdtCostSentence(node.build_count, node.bytes_processed, node.estimated_cost_usd, node.used_by_explores, node.source_file);
    }
    case 'usage': {
      const rest = evId.slice('usage:'.length); // "explore:MODEL.NAME" or "view:NAME"
      if (rest.startsWith('explore:')) {
        const key = rest.slice('explore:'.length);
        const nodeId = exploreNodeIdFromKey(key);
        const node = nodeId ? NODE_BY_ID[nodeId] : null;
        return exploreUsageSentence(key, node ? node.source_file : null);
      }
      return 'no usage is tracked at the view level \u2014 view aliveness is derived structurally' +
        ' from whether any explore still reaches it, not from a query-count fact.';
    }
    case 'pdt_build': {
      const view = evId.slice('pdt_build:'.length);
      const fact = ownFact(L1_FACTS.pdt_build, view);
      if (!fact) return `No PDT build facts were provided for '${view}'.`;
      const node = NODE_BY_ID['pdt:' + view];
      return pdtCostSentence(
        fact.build_count, fact.bytes_processed, fact.estimated_cost_usd,
        node ? node.used_by_explores : null, node ? node.source_file : null
      );
    }
    case 'schema_table': {
      const table = evId.slice('schema_table:'.length);
      const fact = ownFact(L1_FACTS.schema_table, table);
      if (!fact) {
        return `table '${table}' was not found in the provided schema facts \u2014 the resolved IR references it, but no warehouse metadata confirms it exists.`;
      }
      const cols = fact.columns || [];
      const colList = cols.length ? `: ${cols.join(', ')}` : '';
      return `table '${table}' is present in the provided schema facts with ${fact.column_count} known column${fact.column_count !== 1 ? 's' : ''}${colList}.`;
    }
    case 'physical_table': {
      const table = evId.slice('physical_table:'.length);
      const fact = ownFact(L1_FACTS.schema_table, table);
      const scanned = Object.keys(L1_FACTS.schema_table).length;
      if (!fact) {
        return `physical table '${table}' is not present in the provided schema facts (scanned ${scanned} table${scanned !== 1 ? 's' : ''}).`;
      }
      const node = NODE_BY_ID[evId];
      let s = `physical table '${table}' is present in the provided schema facts with ${fact.column_count} known column${fact.column_count !== 1 ? 's' : ''}`;
      if (node && node.source_file) s += ` \u00b7 exists in resolved IR at '${node.source_file}'`;
      return s + '.';
    }
    case 'field':
      return `no field-level L1 fact is tracked for '${evId.slice('field:'.length)}'` +
        ' \u2014 see the table/view evidence alongside this field for usage and schema context.';
    default:
      return `No evidence sentence is defined for the '${namespace}' namespace yet.`;
  }
}

function evidenceHtml(evId) {
  const nodeId = resolveEvidenceNodeId(evId);
  const label = escapeHtml(evId);
  const cls = nodeId ? 'pill ev-chip pill-link' : 'pill ev-chip pill-info';
  const nodeAttr = nodeId ? ` data-node-id="${escapeHtml(nodeId)}"` : '';
  return `<a href="#" class="${cls}" data-ev-id="${label}"${nodeAttr}>${label}</a>`;
}
function evidenceListHtml(ids) { return (ids || []).map(evidenceHtml).join(''); }
// A row's own artifact id (not one of its evidence_ids) — used as the deep-link/copy-link
// target and as the chip that opens the row's headline sentence (dead-explore usage,
// PDT cost/builds) on click. `rowId` lets the copy-link/DOM-anchor target diverge from the
// chip's evidence id — needed for Schema Drift, where several rows share one
// `schema_table:` id (not unique enough for a DOM id) but each row's own SchemaDriftRecord
// id is; defaults to `id` when the two coincide (Dead Code Register, PDT Ledger).
function primaryChipHtml(id, label, rowId) {
  const anchorId = rowId || id;
  const nodeId = resolveEvidenceNodeId(id);
  const cls = nodeId ? 'ev-chip pill-link row-primary-link' : 'ev-chip pill-info row-primary-link';
  const nodeAttr = nodeId ? ` data-node-id="${escapeHtml(nodeId)}"` : '';
  return `<a href="#" class="${cls}" data-ev-id="${escapeHtml(id)}"${nodeAttr}>${escapeHtml(label)}</a>` +
    `<button type="button" class="copy-link-btn" data-copy-hash="${escapeHtml(anchorId)}" title="Copy link to this row">🔗</button>`;
}

function toggleEvidencePanel(chip) {
  // A primary chip (row Name/View cell) has a copy-link <button> immediately after it —
  // anchor the sentence panel after THAT, not the chip, or the sibling check below never
  // finds it and re-clicking stacks duplicate panels instead of toggling.
  const afterChip = chip.nextElementSibling;
  const anchor = (afterChip && afterChip.classList && afterChip.classList.contains('copy-link-btn'))
    ? afterChip : chip;
  const evId = chip.dataset.evId;
  const next = anchor.nextElementSibling;
  if (next && next.classList && next.classList.contains('evidence-sentence')) {
    next.remove();
    return;
  }
  const panel = el('div', 'evidence-sentence');
  panel.textContent = evId + ': ' + evidenceSentence(evId);
  anchor.insertAdjacentElement('afterend', panel);
}
function openHashTarget() {
  const raw = location.hash.slice(1);
  if (!raw) return;
  let id = raw;
  try { id = decodeURIComponent(raw); } catch (e) { id = raw; }
  // Decoded first (the encoded form this build writes), raw second — so a link copied
  // from an older build, where the fragment was written unencoded, still resolves.
  let row = document.getElementById(id);
  if (!row && id !== raw) row = document.getElementById(raw);
  if (!row) return;
  row.scrollIntoView({ behavior: 'smooth', block: 'center' });
  // Plain string equality on dataset — no selector-escaping regex. The escaped-regex
  // version died at parse time in the GENERATED page (non-raw Python string collapsed a
  // backslash layer: /["\\]/g → unterminated class), killing every script on the page.
  // Caught only by the live browser pass — Python tests never execute the JS.
  const chips = Array.from(row.querySelectorAll('.ev-chip'));
  const chip = chips.find(c => c.dataset.evId === id) || chips[0] || null;
  // Idempotent by contract: hash navigation (including Back to an already-open target)
  // must leave the panel OPEN — a toggle here closed it on revisit (Codex P2, PR #28).
  if (chip) openEvidencePanel(chip);
}

function openEvidencePanel(chip) {
  const afterChip = chip.nextElementSibling;
  const anchor = (afterChip && afterChip.classList && afterChip.classList.contains('copy-link-btn'))
    ? afterChip : chip;
  const next = anchor.nextElementSibling;
  if (next && next.classList && next.classList.contains('evidence-sentence')) return; // already open
  toggleEvidencePanel(chip);
}

let CY = null;
// Selects a node, zooms to its direct neighborhood and opens its detail panel. `scroll`
// brings the graph into view first — wanted from a table chip, not from inside the panel.
function focusGraphNode(nodeId, scroll) {
  if (!CY) return;
  const ele = CY.getElementById(nodeId);
  if (!ele || ele.empty()) return;
  const cyEl = document.getElementById('cy');
  if (cyEl && scroll !== false) cyEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  CY.elements(':selected').unselect();
  ele.select();
  ele.emit('tap');
  CY.animate({ fit: { eles: ele.closedNeighborhood(), padding: 70 } }, { duration: 300 });
}
document.addEventListener('click', function(evt) {
  const chip = evt.target.closest('.ev-chip');
  if (chip) {
    evt.preventDefault();
    toggleEvidencePanel(chip);
    if (chip.dataset.nodeId) focusGraphNode(chip.dataset.nodeId);
    return;
  }
  const copyBtn = evt.target.closest('.copy-link-btn');
  if (copyBtn) {
    evt.preventDefault();
    const id = copyBtn.dataset.copyHash;
    // location.origin is the literal string "null" under file:// — and opening
    // dashboard.html directly is a supported posture for this self-contained file.
    // href minus any existing hash is scheme-agnostic (Codex P1, PR #28).
    // encodeURIComponent, because openHashTarget() decodes what it reads. Without the
    // encode the pair is asymmetric: an id holding a literal percent-escape (a quoted
    // physical table like 'foo%20bar') decodes to 'foo bar' on open and matches nothing.
    // Encode-on-write + decode-on-read round-trips every accepted name (Codex, PR #28).
    const url = location.href.split('#')[0] + '#' + encodeURIComponent(id);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(() => {
        const prev = copyBtn.textContent;
        copyBtn.textContent = '✓';
        setTimeout(() => { copyBtn.textContent = prev; }, 1200);
      }).catch(() => {});
    }
  }
});
window.addEventListener('hashchange', openHashTarget);
window.addEventListener('load', openHashTarget);

// ── Hero + KPI Row ───────────────────────────────────────────────────────────
// The headline names the single most expensive problem; the cards follow in the same
// order (attention first), and each one jumps to the section that explains it. Every claim
// is gated on COVERAGE: an empty finding list from a check that never ran (no usage or schema
// facts loaded) is "not run", never "clean" and never 0.
function notRunText(coverage) {
  if (!coverage.usage && !coverage.schema) return 'Usage and schema facts not loaded — dead-code, PDT cost and schema drift checks did not run';
  if (!coverage.usage) return 'Usage facts not loaded — dead-code and PDT cost checks did not run';
  if (!coverage.schema) return 'Schema facts not loaded — the schema drift check did not run';
  return '';
}
function heroCopy(coverage, s, drift, ledger) {
  const dead = s.dead_code_count || 0;
  const deadExplores = s.dead_explore_count || 0;
  const deadViews = s.dead_view_count || 0;
  const pdtUnused = ledger.filter(r => r.status === 'unused' || r.status === 'zombie').reduce((a, r) => a + (r.estimated_cost_usd || 0), 0);
  const windowLabel = s.period ? `${s.period.days}-day window` : 'unknown window';
  const notRun = notRunText(coverage);
  let headline;
  if (coverage.usage && pdtUnused > 0) headline = `${fmt_money(pdtUnused)} of PDT spend backs nothing anyone uses.`;
  else if (coverage.usage && dead > 0) headline = `${plural(dead, 'dead artifact')} ready to retire.`;
  else if (coverage.schema && drift > 0) headline = `${plural(drift, 'schema reference')} point at nothing.`;
  else if (!notRun) headline = 'This repo is clean. Nothing needs attention.';
  else headline = notRun + '.';
  const parts = [];
  if (coverage.usage && dead) parts.push(`${plural(deadExplores, 'dead explore')} and ${plural(deadViews, 'dead view')}`);
  if (coverage.schema && drift) parts.push(plural(drift, 'broken schema reference'));
  let lede = parts.length ? `Also: ${parts.join(', ')}.` : '';
  if (coverage.usage) {
    lede += ` Analysed across ${plural(s.ir_explore_count || 0, 'explore')} and ${(s.total_queries || 0).toLocaleString('en-US')} queries in the ${windowLabel}.`;
  }
  // The not-run notice rides in the lede whenever it isn't already the headline.
  if (notRun && headline !== notRun + '.') lede += ` ${notRun}.`;
  if (!lede.trim()) lede = 'Pass --usage-fixture and --schema-fixture (or --looker-url) to run the usage and drift checks.';
  return { headline: headline, lede: lede.trim() };
}
function kpiCards(coverage, s, drift, ledger) {
  const NOT_RUN = 'Not run';
  const dead = s.dead_code_count || 0;
  const pdtTotal = ledger.reduce((a, r) => a + (r.estimated_cost_usd || 0), 0);
  const pdtUnused = ledger.filter(r => r.status === 'unused' || r.status === 'zombie').reduce((a, r) => a + (r.estimated_cost_usd || 0), 0);
  const windowLabel = s.period ? `${s.period.days}-day window` : 'unknown window';
  const u = coverage.usage;
  const cards = [
    u ? { label: 'PDT spend nothing reads', value: fmt_money(pdtUnused), sub: pdtUnused > 0 ? `of ${fmt_money(pdtTotal)} total, ${windowLabel}` : `all ${fmt_money(pdtTotal)} is in use`, cls: pdtUnused > 0 ? 'caution' : 'ok', href: '#pdt-cost' }
      : { label: 'PDT spend nothing reads', value: NOT_RUN, sub: 'no usage facts loaded', cls: 'skipped', href: '#pdt-cost' },
    u ? { label: 'Dead explores and views', value: dead, sub: `${s.dead_explore_count || 0} explores, ${s.dead_view_count || 0} views`, cls: dead > 0 ? 'warn' : 'ok', href: '#dead-code' }
      : { label: 'Dead explores and views', value: NOT_RUN, sub: 'no usage facts loaded', cls: 'skipped', href: '#dead-code' },
    coverage.schema ? { label: 'Broken schema references', value: drift, sub: 'missing tables or columns', cls: drift > 0 ? 'warn' : 'ok', href: '#drift' }
      : { label: 'Broken schema references', value: NOT_RUN, sub: 'no schema facts loaded', cls: 'skipped', href: '#drift' },
    // active_explore_count is L1's (resolved explores minus dead explores); never re-derived here.
    u ? { label: 'Active explores', value: s.active_explore_count, sub: `of ${s.ir_explore_count || 0} explores`, cls: 'info', href: '#graph' }
      : { label: 'Active explores', value: NOT_RUN, sub: 'no usage facts loaded', cls: 'skipped', href: '#graph' },
    u ? { label: 'Queries', value: (s.total_queries || 0).toLocaleString('en-US'), sub: s.period ? `last ${s.period.days} days` : 'period unknown', cls: 'info', href: '' }
      : { label: 'Queries', value: NOT_RUN, sub: 'no usage facts loaded', cls: 'skipped', href: '' },
  ];
  const rank = { warn: 0, caution: 0, info: 1, ok: 2, skipped: 3 };
  return cards.sort((a, b) => rank[a.cls] - rank[b.cls]);
}
(function() {
  const args = [COVERAGE, USAGE_SUMMARY || {}, (SCHEMA_DRIFT || []).length, PDT_LEDGER || []];
  const copy = heroCopy(...args);
  document.getElementById('hero-headline').textContent = copy.headline;
  document.getElementById('hero-lede').textContent = copy.lede;
  const row = document.getElementById('kpi-row');
  kpiCards(...args).forEach(c => {
    const card = el(c.href ? 'a' : 'div', 'kpi-card ' + (c.cls||''));
    if (c.href) card.setAttribute('href', c.href);
    card.innerHTML = `<div class="label">${escapeHtml(c.label)}</div><div class="value">${escapeHtml(c.value)}</div><div class="sub">${escapeHtml(c.sub)}</div>`;
    row.appendChild(card);
  });
})();

// ── Dead Code Table ───────────────────────────────────────────────────────────
(function() {
  const body = document.getElementById('dead-body');
  const count = document.getElementById('dead-count');
  const items = DEAD_CODE || [];
  count.textContent = items.length + ' item' + (items.length !== 1 ? 's' : '');
  if (!COVERAGE.usage) { body.innerHTML = '<div class="empty skipped">Dead-code check not run: no usage facts loaded.</div>'; count.textContent = 'not run'; return; }
  if (!items.length) { body.innerHTML = '<div class="empty"><div class="icon">✓</div>No dead code detected</div>'; return; }
  const tbl = el('table');
  tbl.innerHTML = '<thead><tr><th>Kind</th><th>Name</th><th>Source file</th><th>Why it is dead</th><th data-sort="none">Evidence</th></tr></thead>';
  const tbody = el('tbody');
  items.forEach(r => {
    const tr = el('tr', 'dead-row');
    tr.id = r.id;
    const kindBadge = r.kind === 'explore' ? 'badge-red' : 'badge-orange';
    const pills = evidenceListHtml(r.evidence_ids);
    tr.innerHTML = `
      <td><span class="badge ${kindBadge}">${escapeHtml(r.kind)}</span></td>
      <td class="mono" style="font-weight:600">${primaryChipHtml(r.id, r.name)}</td>
      <td class="file-tag">${escapeHtml(r.source_file||'')}</td>
      <td>${escapeHtml(r.static_reason||'')}<div class="reason-text">${escapeHtml(r.usage_reason||'')}</div></td>
      <td>${pills}</td>`;
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
  makeSortable(tbl);
  body.appendChild(wrapTable(tbl));
})();

// ── PDT Ledger ────────────────────────────────────────────────────────────────
(function() {
  const body = document.getElementById('pdt-body');
  // Most expensive first: the chart and the table read top-down in the same order.
  const pdts = [...(PDT_LEDGER || [])].sort((a, b) => (b.estimated_cost_usd||0) - (a.estimated_cost_usd||0));
  if (!COVERAGE.usage) { body.innerHTML = '<div class="empty skipped">PDT cost check not run: no usage facts loaded.</div>'; return; }
  if (!pdts.length) { body.innerHTML = '<div class="empty"><div class="icon">✓</div>No PDTs detected</div>'; return; }

  const wrap = el('div', 'pdt-layout');

  // Chart
  const chartWrap = el('div');
  chartWrap.innerHTML = '<div class="chart-wrap"><canvas id="pdt-chart" aria-label="PDT cost by view" role="img"></canvas></div>';
  chartWrap.firstChild.style.height = Math.max(120, pdts.length * 34 + 30) + 'px';
  wrap.appendChild(chartWrap);

  // Table
  const tableWrap = el('div');
  const tbl = el('table');
  tbl.innerHTML = '<thead><tr><th>PDT view</th><th class="num" data-sort="num" aria-sort="descending">Cost / mo</th><th class="num" data-sort="num">Builds</th><th class="num" data-sort="num">Data scanned</th><th>Status</th><th data-sort="none">Used by</th></tr></thead>';
  const tbody = el('tbody');
  pdts.forEach(r => {
    const tr = el('tr');
    const primaryId = 'pdt:' + r.view;
    tr.id = primaryId;
    const isUnused = r.status === 'unused';
    const isZombie = r.status === 'zombie';
    const statusCell = isZombie
      ? `<span class="zombie-badge">⚠ ZOMBIE — ${fmt_usd(r.estimated_cost_usd)}/mo</span>`
      : isUnused
      ? `<span class="kill-badge">⚠ KILL — ${fmt_usd(r.estimated_cost_usd)}/mo</span>`
      : `<span class="badge badge-green">In Use</span>`;
    const costColor = isZombie ? 'var(--purple)' : isUnused ? 'var(--orange)' : 'var(--text)';
    const explores = (r.used_by_explores||[]).map(e => `<div class="file-tag">${escapeHtml(e)}</div>`).join('');
    tr.innerHTML = `
      <td class="mono" style="font-weight:600">${primaryChipHtml(primaryId, r.view)}</td>
      <td class="num" data-sort-value="${Number(r.estimated_cost_usd)}" style="font-weight:600;color:${costColor}">${fmt_usd(r.estimated_cost_usd)}</td>
      <td class="num" data-sort-value="${Number(r.build_count)}">${escapeHtml(r.build_count)}</td>
      <td class="num" data-sort-value="${Number(r.bytes_processed)}">${fmt_bytes(Number(r.bytes_processed))}</td>
      <td>${statusCell}</td>
      <td>${explores || '<span style="color:var(--muted)">none</span>'}</td>`;
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
  makeSortable(tbl);
  tableWrap.appendChild(wrapTable(tbl));
  wrap.appendChild(tableWrap);
  body.appendChild(wrap);

  // Render chart after DOM is ready
  requestAnimationFrame(() => {
    const ctx = document.getElementById('pdt-chart');
    if (!ctx || typeof Chart === 'undefined') return;
    const tok = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    const statusColor = st => tok(st === 'zombie' ? '--n-zombie' : st === 'unused' ? '--n-pdt-unused' : st === 'used' ? '--n-pdt-used' : '--n-pdt-unknown');
    Chart.defaults.font.family = tok('--sans');
    try { new Chart(ctx, {
      type: 'bar',
      data: {
        labels: pdts.map(r => r.view),
        datasets: [{
          label: 'Cost / mo (USD)',
          data: pdts.map(r => r.estimated_cost_usd),
          backgroundColor: pdts.map(r => statusColor(r.status)),
          borderRadius: 4,
          maxBarThickness: 22,
        }]
      },
      options: {
        indexAxis: 'y',
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => ' ' + fmt_usd(Number(c.parsed.x)) + ' / mo' } } },
        scales: {
          x: { ticks: { color: tok('--muted'), callback: v => fmt_money(v) }, grid: { color: tok('--border') }, border: { display: false } },
          y: { ticks: { color: tok('--text-2'), font: { family: tok('--mono'), size: 11 } }, grid: { display: false }, border: { display: false } },
        },
        responsive: true, maintainAspectRatio: false,
      }
    }); } catch(e) { console.error('Chart render error:', e); }
  });
})();

// ── Cleanup Roadmap ───────────────────────────────────────────────────────────
(function() {
  const body = document.getElementById('roadmap-body');
  const count = document.getElementById('roadmap-count');
  const items = [...(ROADMAP||[])].sort((a,b) => (b.estimated_cost_usd||0) - (a.estimated_cost_usd||0));
  count.textContent = items.length + ' action' + (items.length !== 1 ? 's' : '');
  if (!items.length && !(COVERAGE.usage && COVERAGE.schema)) { body.innerHTML = '<div class="empty skipped">No cleanup actions from the checks that ran. Load usage and schema facts to run the rest.</div>'; return; }
  if (!items.length) { body.innerHTML = '<div class="empty"><div class="icon">✓</div>Nothing to clean up</div>'; return; }

  const actionStyle = {
    review_for_deprecation: ['badge-red', 'Deprecate'],
    review_unused_pdt_cost: ['badge-orange', 'Kill PDT'],
    repair_schema_reference: ['badge-blue', 'Repair Schema'],
  };
  const ul = el('ul', 'roadmap-list');
  items.forEach((r, i) => {
    const [cls, label] = actionStyle[r.action] || ['badge-gray', r.action];
    const cost = r.estimated_cost_usd ? ` · saves ${fmt_usd(r.estimated_cost_usd)}/mo` : '';
    const evCount = Number((r.evidence_ids||[]).length);
    // Roadmap items carry no own artifact id — the chip itself resolves via the slice's own
    // evidence_ids[0] (explore:/view:/pdt:/field:, always the record's own namespace per
    // _cleanup_roadmap()) verbatim, unchanged. The DOM anchor/copy-link target is a SEPARATE
    // 'roadmap:' namespace so it can never collide with a ledger/register row's own id —
    // multiple actions can share one primaryId (e.g. two roadmap rows on the same field),
    // so a ':2'/':3' suffix disambiguates within the roadmap itself.
    const primaryId = r.evidence_ids[0];
    const roadmapId = uniqueAnchor('roadmap:' + primaryId);
    const li = el('li', 'roadmap-item');
    li.id = roadmapId;
    li.innerHTML = `
      <div class="roadmap-num">${Number(i + 1)}</div>
      <div class="roadmap-body">
        <span class="badge ${escapeHtml(cls)}">${escapeHtml(label)}</span>
        &nbsp;<span class="roadmap-target">${primaryChipHtml(primaryId, r.target, roadmapId)}</span>
        <div class="roadmap-meta">${escapeHtml(r.kind)}${cost}</div>
        <details class="evidence-details"><summary>${evCount} evidence link${evCount!==1?'s':''}</summary>
          <div class="evidence-list">${evidenceListHtml(r.evidence_ids)}</div>
        </details>
      </div>`;
    ul.appendChild(li);
  });
  body.appendChild(ul);
})();

// ── Schema Drift ──────────────────────────────────────────────────────────────
(function() {
  const body = document.getElementById('drift-body');
  const count = document.getElementById('drift-count');
  const items = SCHEMA_DRIFT || [];
  if (!items.length) {
    count.textContent = '0 issues';
    if (!COVERAGE.schema) {
      count.textContent = 'not run';
      body.innerHTML = '<div class="empty skipped">Schema drift check not run: no schema facts loaded.</div>';
      return;
    }
    body.innerHTML = '<div class="empty"><div class="icon">✓</div>No schema drift detected</div>';
    return;
  }

  // Rows that look byte-identical on the visible columns often differ by `field` — the
  // specific LookML field whose SQL references the drifted column. Group on the FULL
  // fact (field included) and only collapse with a ×N count when rows are truly
  // duplicates even including it; never hide a real distinct field behind a fake dedup.
  const groups = [];
  const byKey = new Map();
  items.forEach(r => {
    const key = [r.kind, r.table, r.column || '', r.field || '', r.source_file, r.reason].join('');
    let g = byKey.get(key);
    if (!g) { g = Object.assign({}, r, { count: 0 }); byKey.set(key, g); groups.push(g); }
    g.count += 1;
  });
  count.textContent = groups.length === items.length
    ? items.length + ' issue' + (items.length !== 1 ? 's' : '')
    : items.length + ' raw hit' + (items.length !== 1 ? 's' : '') + ' · ' + groups.length + ' unique';

  const tbl = el('table');
  tbl.innerHTML = '<thead><tr><th>Kind</th><th>Table / column</th><th>Field</th><th>Source file</th><th>Reason</th><th class="num" data-sort="num">Count</th></tr></thead>';
  const tbody = el('tbody');
  groups.forEach(r => {
    const tr = el('tr', 'dead-row');
    // Row's own SchemaDriftRecord id is the stable DOM anchor/copy-link target (several
    // rows can share one table, so `schema_table:` alone isn't unique enough for that);
    // the chip itself still resolves via `schema_table:`, one of the row's own
    // pre-existing evidence_ids (no new id scheme invented).
    const driftAnchor = uniqueAnchor(r.id);
    tr.id = driftAnchor;
    const chipLabel = (r.table||'') + (r.column ? ' · ' + r.column : '');
    tr.innerHTML = `
      <td><span class="badge badge-red">${escapeHtml(r.kind)}</span></td>
      <td class="mono">${primaryChipHtml('schema_table:' + r.table, chipLabel, driftAnchor)}</td>
      <td class="file-tag">${escapeHtml(r.field||'')}</td>
      <td class="file-tag">${escapeHtml(r.source_file||'')}</td>
      <td class="reason-text">${escapeHtml(r.reason||'')}</td>
      <td class="num" data-sort-value="${Number(r.count)}">${escapeHtml(r.count > 1 ? '\u00d7' + r.count : '')}</td>`;
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
  makeSortable(tbl);
  body.appendChild(wrapTable(tbl));
})();

// ── Migration Impact Accordion ────────────────────────────────────────────────
(function() {
  const body = document.getElementById('migration-body');
  const items = (MIGRATION||[]).filter(r => (r.explores||[]).length > 0);
  if (!items.length) { body.innerHTML = '<div class="empty"><div class="icon">—</div>No migration impact data</div>'; return; }
  items.forEach(r => {
    const item = el('div', 'accordion-item');
    const trigger = el('button', 'accordion-trigger');
    trigger.innerHTML = `<span class="arrow">▶</span><span class="mono">${escapeHtml(r.physical_table)}</span><span style="margin-left:auto;font-size:12px;color:var(--muted)">${Number((r.explores||[]).length)} explore${(r.explores||[]).length!==1?'s':''} affected</span>`;
    trigger.onclick = () => {
      const open = trigger.classList.toggle('open');
      content.classList.toggle('open', open);
    };
    const content = el('div', 'accordion-content');
    content.innerHTML = `<div class="impact-grid">
      <div class="impact-group"><label>Views</label><div class="items">${(r.views||[]).map(v=>`<span class="impact-tag">${escapeHtml(v)}</span>`).join('')||'<span style="color:var(--muted)">none</span>'}</div></div>
      <div class="impact-group"><label>Explores</label><div class="items">${(r.explores||[]).map(v=>`<span class="impact-tag">${escapeHtml(v)}</span>`).join('')}</div></div>
      <div class="impact-group"><label>Fields (${Number((r.fields||[]).length)})</label><div class="items">${(r.fields||[]).slice(0,8).map(v=>`<span class="impact-tag">${escapeHtml(v)}</span>`).join('')}${(r.fields||[]).length>8?`<span style="color:var(--muted);font-size:11px">+${Number((r.fields||[]).length)-8} more</span>`:''}</div></div>
    </div>`;
    item.appendChild(trigger);
    item.appendChild(content);
    body.appendChild(item);
  });
})();

// ── Graph highlight state (top level, no DOM — runnable against headless Cytoscape) ──
function newGraphState() {
  return { query: '', attentionOnly: false, hovered: null, pinned: null, hiddenKinds: new Set() };
}
// A filter change (search text or the attention toggle) drops any pinned selection, so the
// filter's focus set wins; selecting a node afterwards pins again until the next change.
// Returns whether a filter actually changed.
function setGraphFilter(state, patch) {
  const changed = ('query' in patch && patch.query !== state.query) ||
    ('attentionOnly' in patch && patch.attentionOnly !== state.attentionOnly);
  Object.assign(state, patch);
  if (changed) state.pinned = null;
  return changed;
}
function graphFilteredSet(cy, state) {
  // Null = no filter active (everything visible counts as in focus).
  if (!state.query && !state.attentionOnly) return null;
  const q = state.query;
  return cy.nodes().not('.hidden').filter(n => {
    const d = n.data();
    const hit = !q || String(d.label).toLowerCase().includes(q) || String(d.model || '').toLowerCase().includes(q);
    return hit && (!state.attentionOnly || d.attention);
  });
}
// The one place that decides what is hidden, faded, labeled and matched.
function applyGraphState(cy, state) {
  let filtered = null, visible = null;
  cy.batch(() => {
    cy.nodes().forEach(n => n.toggleClass('hidden', state.hiddenKinds.has(n.data('kind'))));
    cy.elements().removeClass('faded hl match');
    visible = cy.nodes().not('.hidden');
    filtered = graphFilteredSet(cy, state);
    if (filtered) {
      if (state.query) filtered.addClass('match');
      cy.elements().not(filtered.closedNeighborhood()).addClass('faded');
      filtered.addClass('hl');
      filtered.connectedEdges().addClass('hl');
    }
    const anchor = state.hovered || state.pinned;
    if (anchor && !anchor.hasClass('hidden')) {
      cy.elements().addClass('faded');
      anchor.closedNeighborhood().removeClass('faded').addClass('hl');
    }
  });
  return { filtered: filtered, visible: visible };
}

// ── Cytoscape Dependency Graph ────────────────────────────────────────────────
// Left-to-right layers (explores, then views, then PDTs and warehouse tables) so labels run
// along each column instead of colliding across a single wide row. Labels show the short
// object name and fade out when zoomed too far to read; hovering or selecting a node always
// labels its neighborhood, and the tooltip/detail panel carry the full name.
(function() {
  const graphContainer = document.getElementById('cy');
  if (typeof cytoscape === 'undefined') {
    if (graphContainer) graphContainer.innerHTML = '<p style="color:var(--muted);padding:24px">Graph library failed to load. Check your network connection.</p>';
    return;
  }
  if (!GRAPH_DATA || !GRAPH_DATA.nodes || GRAPH_DATA.nodes.length === 0) {
    if (graphContainer) graphContainer.innerHTML = '<p style="color:var(--muted);padding:24px">No graph data — run <code>strata outputs --repo /path/to/lookml</code> to build the IR.</p>';
    return;
  }
  try {
    if (typeof cytoscapeDagre !== 'undefined') cytoscape.use(cytoscapeDagre);
  } catch(e) { /* dagre already registered */ }

  const rootStyle = getComputedStyle(document.documentElement);
  const tok = name => rootStyle.getPropertyValue(name).trim();
  const C = { bg: tok('--bg'), text: tok('--text'), text2: tok('--text-2'), muted: tok('--muted'), focus: tok('--focus'), font: tok('--sans') };
  const KIND_LABEL = { explore: 'Explore', view: 'View', pdt: 'PDT', physical_table: 'Physical table' };

  // Display-only: a warehouse table's label drops its project.dataset qualifier; an explore
  // whose name another model shares shows model.explore (display_label, set in Python).
  GRAPH_DATA.nodes.forEach(n => {
    const d = n.data;
    const parts = String(d.label).split('.');
    d.short = d.kind === 'physical_table' ? parts[parts.length - 1] : String(d.display_label || d.label);
  });

  // Size the canvas to the tallest layer (~26px per node) so a big repo opens at a zoom
  // where labels are readable, instead of shrinking everything into an unlabeled column.
  const kindCounts = Object.create(null);
  GRAPH_DATA.nodes.forEach(n => { kindCounts[n.data.kind] = (kindCounts[n.data.kind] || 0) + 1; });
  const tallest = Math.max(kindCounts.explore || 0, kindCounts.view || 0, (kindCounts.pdt || 0) + (kindCounts.physical_table || 0));
  const narrow = window.matchMedia('(max-width: 640px)').matches;
  const desired = Math.max(narrow ? 380 : 460, Math.min(narrow ? 520 : 980, tallest * 26 + 80));
  graphContainer.style.height = desired + 'px';
  // Side-by-side, the panel scrolls within the graph's height; stacked (narrow), it flows.
  if (!window.matchMedia('(max-width: 960px)').matches) document.getElementById('detail-panel').style.maxHeight = desired + 'px';

  const cy = cytoscape({
    container: graphContainer,
    // Mouse: plain wheel scrolls the page; pinch or Cmd/Ctrl+wheel zooms (handled below), so
    // the graph never hijacks page scrolling on its way past. Touch keeps native pinch-zoom.
    userZoomingEnabled: window.matchMedia('(pointer: coarse)').matches,
    elements: [...GRAPH_DATA.nodes, ...GRAPH_DATA.edges],
    minZoom: 0.1,
    maxZoom: 2.5,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'shape': 'data(shape)',
          'width': 'data(size)',
          'height': 'data(size)',
          'label': 'data(short)',
          'font-family': C.font,
          'font-size': 12,
          'color': C.text2,
          'text-valign': 'center',
          'text-halign': 'right',
          'text-margin-x': 7,
          'text-outline-width': 3,
          'text-outline-color': C.bg,
          'text-wrap': 'ellipsis',
          'text-max-width': 170,
          'min-zoomed-font-size': 8,
          'border-width': 0,
          'overlay-opacity': 0,
        }
      },
      // Explores are the leftmost layer: label to the left, clear of their outgoing edges.
      { selector: 'node[kind = "explore"]', style: { 'text-halign': 'left', 'text-margin-x': -7 } },
      // Views sit mid-graph with an outgoing edge to their right: the label rides on that
      // edge inside a background pill, so it stays one node-height tall and never stacks
      // into its neighbor's label.
      { selector: 'node[kind = "view"]', style: { 'width': 26, 'height': 14, 'text-background-color': C.bg, 'text-background-opacity': 0.92, 'text-background-padding': 2, 'text-background-shape': 'roundrectangle' } },
      { selector: 'node[kind = "physical_table"]', style: { 'width': 18, 'height': 16 } },
      // Problems carry a halo so they read at any zoom, even with labels hidden.
      { selector: 'node[?attention]', style: { 'underlay-color': 'data(color)', 'underlay-padding': 5, 'underlay-opacity': 0.22, 'underlay-shape': 'ellipse' } },
      {
        selector: 'edge',
        style: {
          'line-color': 'data(color)',
          'target-arrow-color': 'data(color)',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.65,
          'width': 1.1,
          'curve-style': 'bezier',
          'opacity': 0.38,
        }
      },
      { selector: 'edge[relation = "explore→joined_view"]', style: { 'line-style': 'dashed', 'line-dash-pattern': [5, 4] } },
      { selector: 'edge[relation = "view→physical_table"]', style: { 'line-style': 'dotted' } },
      { selector: '.hidden', style: { 'display': 'none' } },
      { selector: 'node.faded', style: { 'opacity': 0.14, 'text-opacity': 0, 'underlay-opacity': 0 } },
      { selector: 'edge.faded', style: { 'opacity': 0.05 } },
      { selector: 'node.hl', style: { 'min-zoomed-font-size': 0, 'color': C.text, 'z-index': 10 } },
      { selector: 'edge.hl', style: { 'opacity': 0.95, 'width': 1.8, 'z-index': 9 } },
      { selector: 'node.match', style: { 'border-width': 2, 'border-color': C.focus, 'font-weight': 600 } },
      { selector: 'node:selected', style: { 'border-width': 3, 'border-color': C.focus, 'color': C.text, 'font-weight': 600, 'min-zoomed-font-size': 0, 'z-index': 11 } },
    ],
  });
  CY = cy;
  // Unconnected nodes (orphaned views, tables nothing reads) would all land in dagre's first
  // rank and crowd the explore column; they get their own row beneath the layered graph.
  const isolated = cy.nodes().filter(n => n.degree(false) === 0);
  const connected = cy.elements().not(isolated);
  let isolatedRow = null;
  if (connected.nonempty()) {
    connected.layout({ name: 'dagre', rankDir: 'LR', nodeSep: 12, rankSep: 210, edgeSep: 6, fit: false }).run();
  }
  if (isolated.nonempty()) {
    const bb = connected.nonempty() ? connected.boundingBox() : { x1: 0, y2: 0, w: 900 };
    const colW = 230, rowH = 34;
    const perRow = Math.max(1, Math.floor(Math.max(bb.w, 3 * colW) / colW));
    const top = bb.y2 + (connected.nonempty() ? 96 : 40);
    isolated.sort((a, b) => String(a.data('label')).localeCompare(String(b.data('label')))).forEach((n, i) => {
      n.position({ x: bb.x1 + 10 + (i % perRow) * colW, y: top + Math.floor(i / perRow) * rowH });
    });
    isolatedRow = { x: bb.x1, y: top - 44 };
  }
  cy.fit(cy.elements(), 48);
  graphContainer.addEventListener('wheel', e => {
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    const rect = graphContainer.getBoundingClientRect();
    const level = cy.zoom() * Math.exp(-e.deltaY * 0.0025);
    cy.zoom({ level: level, renderedPosition: { x: e.clientX - rect.left, y: e.clientY - rect.top } });
  }, { passive: false });

  // ── Layer headers: one pill per rank column, tracking pan/zoom ─────────────
  const lanesEl = document.getElementById('cy-lanes');
  const LANE_LABEL = { explore: 'Explores', view: 'Views', pdt: 'PDTs & tables', physical_table: 'PDTs & tables' };
  let lanes = [];
  function computeLanes() {
    const cols = [];
    cy.nodes().not(isolated).forEach(n => {
      const x = n.position('x');
      let col = cols.find(c => Math.abs(c.x - x) < 40);
      if (!col) { col = { x: x, kinds: Object.create(null) }; cols.push(col); }
      col.kinds[n.data('kind')] = (col.kinds[n.data('kind')] || 0) + 1;
    });
    cols.sort((a, b) => a.x - b.x);
    lanes = cols.map(c => {
      const top = Object.keys(c.kinds).sort((a, b) => c.kinds[b] - c.kinds[a])[0];
      return { x: c.x, y: null, label: LANE_LABEL[top] || top };
    });
    if (isolatedRow) lanes.push({ x: isolatedRow.x, y: isolatedRow.y, label: 'Not connected to anything', row: true });
    lanesEl.textContent = '';
    lanes.forEach(l => {
      const pill = el('div', 'cy-lane');
      pill.textContent = l.label;
      lanesEl.appendChild(pill);
      l.el = pill;
    });
    placeLanes();
  }
  function placeLanes() {
    const z = cy.zoom(), pan = cy.pan(), w = graphContainer.clientWidth;
    const h = graphContainer.clientHeight;
    lanes.forEach(l => {
      const x = l.x * z + pan.x;
      if (l.row) {
        const y = l.y * z + pan.y;
        l.el.style.left = Math.max(8, x) + 'px';
        l.el.style.top = y + 'px';
        l.el.style.transform = 'none';
        l.el.style.display = (y < 40 || y > h - 20) ? 'none' : '';
        return;
      }
      l.el.style.left = x + 'px';
      l.el.style.display = (x < 30 || x > w - 30) ? 'none' : '';
    });
  }
  cy.on('viewport resize', placeLanes);
  computeLanes();

  // ── Filter / highlight state — graphState is read by applyGraphState() (top level) ──
  const searchInput = document.getElementById('cy-search');
  const attentionBtn = document.getElementById('cy-attention');
  const countEl = document.getElementById('cy-count');
  const focusBtn = document.getElementById('cy-focus');
  const kindChips = Array.from(document.querySelectorAll('.chip[data-kind]'));
  const state = newGraphState();
  function applyState() {
    const r = applyGraphState(cy, state);
    countEl.textContent = r.filtered
      ? `${r.filtered.length} of ${r.visible.length} nodes match`
      : `${r.visible.length} nodes, ${cy.edges().filter(e => e.visible()).length} edges`;
    focusBtn.disabled = !state.pinned;
  }
  // Every search/attention change goes through here: a filter change drops the pinned
  // selection (and resets the panel), so the filter's results are what the graph shows.
  function changeFilter(patch) {
    const hadPin = !!state.pinned;
    if (setGraphFilter(state, patch) && hadPin) clearSelection();
    applyState();
  }

  function fitTo(eles, pad) {
    const target = eles && eles.nonempty() ? eles : cy.elements().not('.hidden');
    cy.animate({ fit: { eles: target, padding: pad || 40 } }, { duration: 260 });
  }

  let searchTimer = null;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => changeFilter({ query: searchInput.value.trim().toLowerCase() }), 90);
  });
  searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') {
      changeFilter({ query: searchInput.value.trim().toLowerCase() });
      const f = graphFilteredSet(cy, state);
      if (f && f.length === 1) focusGraphNode(f.id(), false);
      else if (f && f.nonempty()) fitTo(f.closedNeighborhood(), 50);
    } else if (e.key === 'Escape') {
      searchInput.value = '';
      changeFilter({ query: '' });
    }
  });
  kindChips.forEach(chip => chip.addEventListener('click', () => {
    const kind = chip.dataset.kind;
    const on = chip.getAttribute('aria-pressed') !== 'true';
    chip.setAttribute('aria-pressed', String(on));
    if (on) state.hiddenKinds.delete(kind); else state.hiddenKinds.add(kind);
    if (state.pinned && state.hiddenKinds.has(state.pinned.data('kind'))) clearSelection();
    applyState();
  }));
  attentionBtn.addEventListener('click', () => {
    changeFilter({ attentionOnly: !state.attentionOnly });
    attentionBtn.setAttribute('aria-pressed', String(state.attentionOnly));
    const f = graphFilteredSet(cy, state);
    fitTo(f ? f.closedNeighborhood() : null, 50);
  });

  // ── Controls ───────────────────────────────────────────────────────────────
  const zoomAt = factor => cy.animate({
    zoom: { level: cy.zoom() * factor, renderedPosition: { x: graphContainer.clientWidth / 2, y: graphContainer.clientHeight / 2 } },
  }, { duration: 140 });
  document.getElementById('cy-zoom-in').addEventListener('click', () => zoomAt(1.3));
  document.getElementById('cy-zoom-out').addEventListener('click', () => zoomAt(1 / 1.3));
  document.getElementById('cy-fit').addEventListener('click', () => fitTo(null, 40));
  focusBtn.addEventListener('click', () => { if (state.pinned) fitTo(state.pinned.closedNeighborhood(), 60); });
  document.getElementById('cy-reset').addEventListener('click', () => {
    searchInput.value = '';
    setGraphFilter(state, { query: '', attentionOnly: false });
    attentionBtn.setAttribute('aria-pressed', 'false');
    state.hiddenKinds.clear();
    kindChips.forEach(c => c.setAttribute('aria-pressed', 'true'));
    clearSelection();
    applyState();
    fitTo(null, 40);
  });

  // ── Hover: trace the neighborhood + tooltip with the full name ───────────────
  const tip = document.getElementById('cy-tip');
  const hint = document.getElementById('cy-hint');
  cy.on('mouseover', 'node', evt => {
    state.hovered = evt.target;
    applyState();
    const d = state.hovered.data();
    tip.textContent = '';
    const name = el('div', 'tip-name');
    name.textContent = d.kind === 'explore' && d.model ? `${d.model}.${d.label}` : d.label;
    const meta = el('div', 'tip-meta');
    const deg = state.hovered.connectedEdges().length;
    meta.textContent = `${KIND_LABEL[d.kind] || d.kind} · ${plural(deg, 'connection')}`;
    tip.appendChild(name);
    tip.appendChild(meta);
    tip.style.display = 'block';
  });
  cy.on('mousemove', 'node', evt => {
    const p = evt.renderedPosition;
    const w = graphContainer.clientWidth;
    const left = Math.min(p.x + 14, w - tip.offsetWidth - 8);
    tip.style.left = Math.max(8, left) + 'px';
    tip.style.top = (p.y + 16) + 'px';
  });
  cy.on('mouseout', 'node', () => {
    state.hovered = null;
    tip.style.display = 'none';
    applyState();
  });
  cy.one('viewport', () => { if (hint) hint.style.display = 'none'; });

  // Detail panel on click — every field below is sourced Python-side in
  // _build_graph_data (one source per fact); this only formats what the node already
  // carries, it never re-derives a verdict from raw artifacts.
  const panel = document.getElementById('detail-content');
  function detailRow(key, valHtml) {
    return `<div class="detail-row"><div class="key">${escapeHtml(key)}</div><div class="val">${valHtml}</div></div>`;
  }
  function consumerListHtml(list) {
    if (!list || !list.length) return '<span style="color:var(--muted)">none</span>';
    return list.map(c => `<div class="consumer-row">${escapeHtml(c.key)}${c.dead ? ' <span style="color:var(--red)">(dead)</span>' : ''}</div>`).join('');
  }
  function statusBadge(d) {
    if (d.kind === 'explore') {
      if (d.status === 'unknown') return '<span class="badge badge-gray">UNKNOWN</span>';
      return d.dead ? '<span class="badge badge-red">DEPRECATE</span>' : '<span class="badge badge-green">KEEP</span>';
    }
    if (d.kind === 'pdt') {
      if (d.status === 'zombie') return '<span class="zombie-badge">⚠ ZOMBIE</span>';
      if (d.status === 'unused') return '<span class="badge badge-orange">⚠ UNUSED</span>';
      if (d.status === 'used') return '<span class="badge badge-green">IN USE</span>';
      return '<span class="badge badge-gray">NO BUILD DATA</span>';
    }
    if (d.kind === 'view') {
      if (d.status === 'orphaned') return '<span class="badge badge-gray">ORPHANED</span>';
      if (d.status === 'zombie_view') return '<span class="zombie-badge">⚠ ZOMBIE VIEW</span>';
      // Blue, not green: the legend renders views blue; green is already claimed by
      // active explores and in-use PDTs (Codex P2, PR #25 — status colors must match the legend).
      return '<span class="badge badge-blue">ACTIVE</span>';
    }
    return '';
  }
  // Clickable list of a node's direct neighbors, built with textContent (no markup from data).
  function neighborList(title, nodes) {
    if (!nodes.length) return null;
    const row = el('div', 'detail-row');
    const key = el('div', 'key');
    key.textContent = `${title} (${nodes.length})`;
    const list = el('div', 'nbr-list');
    nodes.sort((a, b) => String(a.data('label')).localeCompare(String(b.data('label')))).forEach(n => {
      const btn = el('button', 'nbr-btn');
      btn.type = 'button';
      btn.dataset.nbrId = n.id();
      btn.title = n.data('label');
      const dot = el('span', 'dot');
      dot.style.background = n.data('color');
      const name = el('span', 'nbr-name');
      name.textContent = n.data('short');
      const kind = el('span', 'nbr-kind');
      kind.textContent = KIND_LABEL[n.data('kind')] || n.data('kind');
      btn.appendChild(dot);
      btn.appendChild(name);
      btn.appendChild(kind);
      list.appendChild(btn);
    });
    row.appendChild(key);
    row.appendChild(list);
    return row;
  }
  function clearSelection() {
    state.pinned = null;
    cy.elements(':selected').unselect();
    panel.className = 'detail-empty';
    panel.innerHTML = '<strong>Nothing selected</strong>Click a node to see its status, cost and what depends on it. Evidence chips in the tables below also jump here.';
    const start = neighborList('Start here: needs attention', cy.nodes('[?attention]').toArray());
    if (start) { start.classList.add('start-here'); panel.appendChild(start); }
  }

  cy.on('tap', 'node', function(evt) {
    const node = evt.target;
    if (state.hiddenKinds.has(node.data('kind'))) {
      state.hiddenKinds.delete(node.data('kind'));
      kindChips.forEach(c => { if (c.dataset.kind === node.data('kind')) c.setAttribute('aria-pressed', 'true'); });
    }
    state.pinned = node;
    if (!node.selected()) { cy.elements(':selected').unselect(); node.select(); }
    const d = node.data();
    const rows = [];
    rows.push(detailRow('Name', `<span style="font-family:var(--mono);font-weight:600">${escapeHtml(d.label)}</span>`));
    rows.push(detailRow('Kind', `<span class="badge badge-blue">${escapeHtml(d.kind)}</span>`));
    rows.push(detailRow('Status', statusBadge(d)));
    if (d.model) rows.push(detailRow('Model', escapeHtml(d.model)));

    if (d.kind === 'explore') {
      rows.push(detailRow('Query Count', (d.query_count||0).toLocaleString()));
      if ((d.pdt_dependencies||[]).length) {
        rows.push(detailRow('PDT Dependencies', d.pdt_dependencies.map(p => `<span class="pill">${escapeHtml(p)}</span>`).join('')));
      }
    } else if (d.kind === 'pdt') {
      rows.push(detailRow('Cost / mo', fmt_usd(d.estimated_cost_usd||0)));
      rows.push(detailRow('Build Count', (d.build_count||0).toLocaleString()));
      rows.push(detailRow('Data Scanned', fmt_bytes(Number(d.bytes_processed||0))));
      rows.push(detailRow('Used By', consumerListHtml(d.used_by_explores)));
    } else if (d.kind === 'view') {
      rows.push(detailRow('Referencing Explores', consumerListHtml(d.referencing_explores)));
    } else if (d.kind === 'physical_table') {
      const views = d.referencing_views || [];
      rows.push(detailRow('Referencing Views', `${Number(views.length)} view${views.length!==1?'s':''}`));
      if (views.length) {
        rows.push(detailRow('Views', views.map(v => `<span class="pill">${escapeHtml(v)}</span>`).join('')));
      }
    }

    rows.push(detailRow('Source File', `<span class="file-tag">${escapeHtml(d.source_file||'')}</span>`));
    panel.className = '';
    panel.innerHTML = rows.join('');
    const up = neighborList('Upstream', node.incomers('node').toArray());
    const down = neighborList('Downstream', node.outgoers('node').toArray());
    if (up) panel.appendChild(up);
    if (down) panel.appendChild(down);
    applyState();
  });
  panel.addEventListener('click', evt => {
    const btn = evt.target.closest('.nbr-btn');
    if (btn) focusGraphNode(btn.dataset.nbrId, false);
  });

  cy.on('tap', function(evt) {
    if (evt.target === cy) { clearSelection(); applyState(); }
  });
  clearSelection();
  applyState();
})();
</script>
</body>
</html>
"""
