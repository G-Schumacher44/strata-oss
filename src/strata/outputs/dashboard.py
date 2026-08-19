"""Generate a self-contained HTML observability dashboard from Strata artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strata.ir.types import IRGraph
from strata.l1.enrich import view_consumer_map


def _read_js(filename: str) -> str:
    js_dir = Path(__file__).resolve().parent.parent / "assets" / "js"
    return (js_dir / filename).read_text(encoding="utf-8")


def build_dashboard_html(artifacts: dict[str, Any], graph: IRGraph) -> str:
    graph_data = _build_graph_data(graph)
    catalog = json.dumps(artifacts.get("catalog", []))
    dead_code = json.dumps(artifacts.get("dead_code_register", []))
    pdt_ledger = json.dumps(artifacts.get("pdt_ledger", []))
    roadmap = json.dumps(artifacts.get("cleanup_roadmap", []))
    schema_drift = json.dumps(artifacts.get("schema_drift", []))
    usage_summary = json.dumps(artifacts.get("usage_summary") or {})
    migration = json.dumps(artifacts.get("migration_impact", []))
    graph_json = json.dumps(graph_data)
    data_block = (
        f"const CATALOG       = {catalog};\n"
        f"const DEAD_CODE     = {dead_code};\n"
        f"const PDT_LEDGER    = {pdt_ledger};\n"
        f"const ROADMAP       = {roadmap};\n"
        f"const SCHEMA_DRIFT  = {schema_drift};\n"
        f"const USAGE_SUMMARY = {usage_summary};\n"
        f"const MIGRATION     = {migration};\n"
        f"const GRAPH_DATA    = {graph_json};\n"
    )
    scripts = "\n".join(
        [
            f"<script>{_read_js('cytoscape.min.js')}</script>",
            f"<script>{_read_js('dagre.min.js')}</script>",
            f"<script>{_read_js('cytoscape-dagre.min.js')}</script>",
            f"<script>{_read_js('chart.umd.min.js')}</script>",
        ]
    )
    return _HTML_TEMPLATE.replace("/*__DATA__*/", data_block).replace("/*__SCRIPTS__*/", scripts)


def _build_graph_data(graph: IRGraph) -> dict[str, Any]:
    l1 = graph.metadata.get("l1", {})
    dead_ids = {r["name"] for r in l1.get("dead_code", [])}
    _eu = l1.get("explore_usage", {})
    usage_map = (
        {k: v["query_count"] for k, v in _eu.items()}
        if isinstance(_eu, dict)
        else {f"{r['model']}.{r['explore']}": r["query_count"] for r in _eu if isinstance(r, dict)}
    )
    pdt_records = {r["view"]: r for r in l1.get("pdt_ledger", [])}

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
            (f"{model}.{node.name}" in dead_ids)
            if node.kind == "explore"
            else (node.name in dead_ids)
        )
        qcount = usage_map.get(f"{model}.{node.name}", 0) if node.kind == "explore" else 0
        is_orphan_struct = bool(node.attrs.get("orphan", False))
        orphan = is_orphan_struct or is_dead

        extra: dict[str, Any] = {}
        if node.kind == "explore":
            views_for_explore = explore_views.get(node.id, [])
            extra["pdt_dependencies"] = sorted(
                {view_pdt[v] for v in views_for_explore if v in view_pdt}
            )
            color = "#e74c3c" if is_dead else "#2ecc71"
            shape = "ellipse"
            size = max(40, min(80, 40 + qcount // 20))
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
            color = (
                "#9b59b6"
                if status == "zombie"
                else "#f39c12"
                if status == "unused"
                else "#2ecc71"
                if status == "used"
                else "#8892a4"  # missing_build_facts — no cost data to render a verdict from
            )
            shape = "diamond"
            size = 36
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
            color = "#95a5a6" if is_orphan_struct else "#9b59b6" if is_zombie_view else "#3498db"
            shape = "ellipse"
            size = 28
        else:  # physical_table
            extra["referencing_views"] = table_views.get(node.name, [])
            color = "#2c3e50"
            shape = "rectangle"
            size = 20

        nodes.append(
            {
                "data": {
                    "id": node.id,
                    "label": node.name,
                    "kind": node.kind,
                    "source_file": node.source_file,
                    "dead": is_dead,
                    "orphan": orphan,
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

        color_map = {
            "explore→base_view": "#ecf0f1",
            "explore→joined_view": "#7f8c8d",
            "view→physical_table": "#4a4a5a",
            "view→pdt": "#f39c12",
        }
        edges.append(
            {
                "data": {
                    "id": f"{edge.source}__{edge.target}",
                    "source": edge.source,
                    "target": edge.target,
                    "relation": edge.relation,
                    "color": color_map.get(edge.relation, "#555"),
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
  --bg: #13151a;
  --surface: #1e2130;
  --surface2: #252840;
  --border: #2e3248;
  --text: #e2e8f0;
  --muted: #8892a4;
  --green: #2ecc71;
  --red: #e74c3c;
  --orange: #f39c12;
  --blue: #3498db;
  --purple: #9b59b6;
  --radius: 10px;
}
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; font-size: 14px; line-height: 1.6; }
a { color: var(--blue); text-decoration: none; }

/* Layout */
.page { max-width: 1400px; margin: 0 auto; padding: 24px 20px 60px; }
header { display: flex; align-items: center; gap: 16px; margin-bottom: 32px; padding-bottom: 20px; border-bottom: 1px solid var(--border); }
header h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }
header .subtitle { color: var(--muted); font-size: 13px; }
.badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
.badge-green { background: rgba(46,204,113,.15); color: var(--green); }
.badge-red { background: rgba(231,76,60,.15); color: var(--red); }
.badge-orange { background: rgba(243,156,18,.15); color: var(--orange); }
.badge-blue { background: rgba(52,152,219,.15); color: var(--blue); }
.badge-gray { background: rgba(136,146,164,.12); color: var(--muted); }

/* KPI Row */
.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 28px; }
.kpi-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px 20px; }
.kpi-card .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.8px; color: var(--muted); margin-bottom: 8px; }
.kpi-card .value { font-size: 28px; font-weight: 700; line-height: 1; }
.kpi-card .sub { font-size: 12px; color: var(--muted); margin-top: 6px; }
.kpi-card.warn .value { color: var(--red); }
.kpi-card.ok .value { color: var(--green); }
.kpi-card.info .value { color: var(--blue); }
.kpi-card.caution .value { color: var(--orange); }

/* Section cards */
.section { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); margin-bottom: 20px; overflow: hidden; }
.section-header { display: flex; align-items: center; gap: 12px; padding: 16px 20px; border-bottom: 1px solid var(--border); }
.section-header h2 { font-size: 15px; font-weight: 600; }
.section-header .count { font-size: 12px; color: var(--muted); margin-left: auto; }
.section-body { padding: 20px; }

/* Graph */
#cy-container { display: flex; gap: 16px; }
.cy-wrap { position: relative; flex: 1; }
#cy { width: 100%; height: 640px; background: var(--bg); border-radius: 8px; border: 1px solid var(--border); }
.cy-controls { position: absolute; top: 12px; right: 12px; display: flex; flex-direction: column; gap: 6px; z-index: 5; }
.cy-btn { width: 30px; height: 30px; border-radius: 6px; border: 1px solid var(--border); background: rgba(30,33,48,.85); color: var(--text); font-size: 16px; line-height: 1; cursor: pointer; }
.cy-btn:hover { background: var(--surface2); border-color: var(--blue); color: var(--blue); }
#detail-panel { width: 300px; background: var(--surface2); border-radius: 8px; border: 1px solid var(--border); padding: 16px; overflow-y: auto; max-height: 640px; }
#detail-panel h3 { font-size: 13px; font-weight: 600; margin-bottom: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; }
.detail-row { margin-bottom: 10px; }
.detail-row .key { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }
.detail-row .val { font-size: 13px; word-break: break-all; }
.detail-empty { color: var(--muted); font-size: 13px; text-align: center; padding: 40px 0; }
.consumer-row { font-size: 12px; font-family: monospace; margin-bottom: 2px; }
.legend { display: flex; flex-wrap: wrap; gap: 14px; padding: 12px 0 0; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.legend-rect { width: 12px; height: 7px; border-radius: 2px; flex-shrink: 0; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--muted); padding: 8px 12px; border-bottom: 1px solid var(--border); font-weight: 600; }
td { padding: 10px 12px; border-bottom: 1px solid rgba(46,50,72,.6); vertical-align: top; }
tr:last-child td { border-bottom: none; }
tr.dead-row td { background: rgba(231,76,60,.04); }
.file-tag { font-size: 11px; color: var(--muted); font-family: monospace; }
.reason-text { color: var(--muted); font-size: 12px; margin-top: 3px; }
.pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 10px; font-weight: 600; margin: 2px 2px 0 0; background: rgba(136,146,164,.1); color: var(--muted); font-family: monospace; }
a.pill-link { cursor: pointer; border: 1px solid transparent; }
a.pill-link:hover { background: rgba(52,152,219,.2); color: var(--blue); border-color: var(--blue); }
.evidence-plain { display: inline-block; font-size: 11px; color: var(--muted); font-family: monospace; margin: 2px 8px 0 0; }
.evidence-details summary { cursor: pointer; font-size: 12px; color: var(--muted); }
.evidence-details summary:hover { color: var(--blue); }
.evidence-list { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 2px; }

/* PDT section */
.pdt-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.chart-wrap { position: relative; height: 160px; }
.kill-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; background: rgba(231,76,60,.2); color: var(--red); }
.zombie-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; background: rgba(155,89,182,.2); color: var(--purple); }

/* Roadmap */
.roadmap-list { list-style: none; }
.roadmap-item { display: flex; align-items: flex-start; gap: 12px; padding: 12px 0; border-bottom: 1px solid rgba(46,50,72,.6); }
.roadmap-item:last-child { border-bottom: none; }
.roadmap-num { width: 24px; height: 24px; border-radius: 50%; background: var(--surface2); display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; color: var(--muted); flex-shrink: 0; margin-top: 1px; }
.roadmap-body { flex: 1; }
.roadmap-target { font-weight: 600; font-size: 13px; font-family: monospace; }
.roadmap-meta { font-size: 12px; color: var(--muted); margin-top: 2px; }

/* Accordion */
.accordion-item { border-bottom: 1px solid rgba(46,50,72,.6); }
.accordion-item:last-child { border-bottom: none; }
.accordion-trigger { width: 100%; text-align: left; background: none; border: none; color: var(--text); font-size: 13px; padding: 12px 0; cursor: pointer; display: flex; align-items: center; gap: 8px; font-family: inherit; }
.accordion-trigger:hover { color: var(--blue); }
.accordion-trigger .arrow { transition: transform .2s; font-size: 10px; color: var(--muted); }
.accordion-trigger.open .arrow { transform: rotate(90deg); }
.accordion-content { display: none; padding: 0 0 14px 20px; }
.accordion-content.open { display: block; }
.impact-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.impact-group label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.6px; color: var(--muted); display: block; margin-bottom: 6px; }
.impact-group .items { display: flex; flex-direction: column; gap: 3px; }
.impact-tag { font-size: 11px; font-family: monospace; color: var(--text); background: var(--surface2); padding: 2px 7px; border-radius: 4px; display: inline-block; }

/* Empty state */
.empty { text-align: center; padding: 32px; color: var(--muted); font-size: 13px; }
.empty .icon { font-size: 28px; margin-bottom: 8px; }

/* Tooltip */
.tooltip-def { border-bottom: 1px dashed var(--muted); cursor: help; }
</style>
</head>
<body>
<div class="page">

<header>
  <div>
    <h1>⬡ Strata</h1>
    <div class="subtitle">LookML Repo Health Dashboard — deterministic analysis, zero tokens</div>
    <div id="period-tag" style="font-size:11px;color:var(--muted);margin-top:4px"></div>
  </div>
</header>

<!-- KPI Row -->
<div class="kpi-row" id="kpi-row"></div>

<!-- Dependency Graph -->
<div class="section">
  <div class="section-header">
    <h2>Dependency Graph</h2>
    <span style="font-size:12px;color:var(--muted)">Explores → Views → Physical Tables &nbsp;·&nbsp; Click any node to inspect</span>
  </div>
  <div class="section-body">
    <div id="cy-container">
      <div class="cy-wrap">
        <div id="cy"></div>
        <div class="cy-controls">
          <button type="button" class="cy-btn" id="cy-zoom-in" title="Zoom in">+</button>
          <button type="button" class="cy-btn" id="cy-zoom-out" title="Zoom out">&minus;</button>
          <button type="button" class="cy-btn" id="cy-fit" title="Fit to view">&#10530;</button>
        </div>
      </div>
      <div id="detail-panel">
        <h3>Node Detail</h3>
        <div id="detail-content" class="detail-empty">Click a node to see details</div>
      </div>
    </div>
    <div class="legend" id="graph-legend">
      <div class="legend-item"><div class="legend-dot" style="background:var(--green)"></div> Active explore</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--red)"></div> Dead explore</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--blue)"></div> View</div>
      <div class="legend-item"><div class="legend-dot" style="background:#95a5a6"></div> Orphaned view</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--purple)"></div> Zombie view / Zombie PDT</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--orange)"></div> PDT (unused)</div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--green)"></div> PDT (in use)</div>
      <div class="legend-item"><div class="legend-rect" style="background:#2c3e50"></div> Physical table</div>
    </div>
  </div>
</div>

<!-- Dead Code -->
<div class="section">
  <div class="section-header">
    <h2>Dead Code Register</h2>
    <span class="count" id="dead-count"></span>
  </div>
  <div class="section-body" id="dead-body"></div>
</div>

<!-- PDT Ledger -->
<div class="section">
  <div class="section-header">
    <h2>PDT Cost Ledger</h2>
    <span style="font-size:12px;color:var(--muted)"><span class="tooltip-def" title="Persistent Derived Table — a precomputed query stored in your warehouse that rebuilds on a schedule">PDT</span> = Persistent Derived Table</span>
  </div>
  <div class="section-body" id="pdt-body"></div>
</div>

<!-- Cleanup Roadmap -->
<div class="section">
  <div class="section-header">
    <h2>Cleanup Roadmap</h2>
    <span class="count" id="roadmap-count"></span>
  </div>
  <div class="section-body" id="roadmap-body"></div>
</div>

<!-- Schema Drift -->
<div class="section">
  <div class="section-header">
    <h2>Schema Drift</h2>
    <span class="count" id="drift-count"></span>
  </div>
  <div class="section-body" id="drift-body"></div>
</div>

<!-- Migration Impact -->
<div class="section">
  <div class="section-header">
    <h2>Migration Impact</h2>
    <span style="font-size:12px;color:var(--muted)">What breaks if a physical table changes?</span>
  </div>
  <div class="section-body" id="migration-body"></div>
</div>

</div><!-- .page -->

<script>
/*__DATA__*/

// ── Period tag ───────────────────────────────────────────────────────────────
(function() {
  const p = USAGE_SUMMARY && USAGE_SUMMARY.period;
  const tag = document.getElementById('period-tag');
  if (tag && p) {
    tag.textContent = p.start + ' → ' + p.end + ' · ' + p.days + '-day window';
  } else if (tag) {
    tag.textContent = 'period unknown — provide a usage fixture';
  }
})();

// ── Helpers ──────────────────────────────────────────────────────────────────
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}
function fmt_bytes(b) {
  if (b >= 1e12) return (b/1e12).toFixed(1) + ' TB';
  if (b >= 1e9)  return (b/1e9).toFixed(1) + ' GB';
  if (b >= 1e6)  return (b/1e6).toFixed(1) + ' MB';
  return b + ' B';
}
function fmt_usd(v) { return '$' + v.toFixed(2); }
function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// ── Evidence linking ────────────────────────────────────────────────────────
// Resolves an evidence id to a graph node id when one exists, so Dead Code Register
// pills and Roadmap evidence links can jump into the graph instead of sitting inert.
const GRAPH_NODE_IDS = new Set((GRAPH_DATA && GRAPH_DATA.nodes || []).map(n => n.data.id));
function resolveEvidenceNodeId(evId) {
  if (!evId) return null;
  if (GRAPH_NODE_IDS.has(evId)) return evId;
  // dead:explore:MODEL.NAME -> explore:MODEL:NAME (dead-code register keys explores
  // model.name-qualified; graph node ids key them model:name — same identity, different separator).
  const m = /^dead:explore:(.+)$/.exec(evId);
  if (m) {
    const dot = m[1].indexOf('.');
    if (dot > -1) {
      const candidate = `explore:${m[1].slice(0, dot)}:${m[1].slice(dot + 1)}`;
      if (GRAPH_NODE_IDS.has(candidate)) return candidate;
    }
  }
  return null;
}
function evidenceHtml(evId) {
  const nodeId = resolveEvidenceNodeId(evId);
  const label = escapeHtml(evId);
  return nodeId
    ? `<a href="#" class="pill pill-link" data-node-id="${escapeHtml(nodeId)}">${label}</a>`
    : `<span class="evidence-plain">${label}</span>`;
}
function evidenceListHtml(ids) { return (ids || []).map(evidenceHtml).join(''); }

let CY = null;
function focusGraphNode(nodeId) {
  if (!CY) return;
  const ele = CY.getElementById(nodeId);
  if (!ele || ele.empty()) return;
  const cyEl = document.getElementById('cy');
  if (cyEl) cyEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  CY.elements(':selected').unselect();
  ele.select();
  CY.animate({ fit: { eles: ele, padding: 120 } }, { duration: 300 });
  ele.emit('tap');
}
document.addEventListener('click', function(evt) {
  const target = evt.target.closest('.pill-link');
  if (!target) return;
  evt.preventDefault();
  focusGraphNode(target.dataset.nodeId);
});

// ── KPI Row ───────────────────────────────────────────────────────────────────
(function() {
  const s = USAGE_SUMMARY;
  const dead = (DEAD_CODE || []).length;
  const active = (s.explore_count || 0) - dead;
  const pdt_total = (PDT_LEDGER || []).reduce((a,r) => a + (r.estimated_cost_usd||0), 0);
  const pdt_unused = (PDT_LEDGER || []).filter(r => r.status === 'unused' || r.status === 'zombie').reduce((a,r) => a + (r.estimated_cost_usd||0), 0);

  const cards = [
    { label: 'Active Explores', value: active, sub: `${dead} dead`, cls: dead > 0 ? '' : 'ok' },
    { label: 'Dead Artifacts', value: dead, sub: 'views + explores', cls: dead > 0 ? 'warn' : 'ok' },
    { label: 'Total Queries', value: (s.total_queries||0).toLocaleString(), sub: s.period ? `last ${s.period.days} days` : 'period unknown', cls: 'info' },
    { label: s.period ? `PDT Cost / ${s.period.days}d` : 'PDT Cost / mo', value: fmt_usd(pdt_total), sub: pdt_unused > 0 ? fmt_usd(pdt_unused) + ' at risk' : 'all in use', cls: pdt_unused > 0 ? 'caution' : '' },
    { label: 'Schema Drift', value: (SCHEMA_DRIFT||[]).length, sub: 'missing tables / columns', cls: (SCHEMA_DRIFT||[]).length > 0 ? 'warn' : 'ok' },
  ];
  const row = document.getElementById('kpi-row');
  cards.forEach(c => {
    const card = el('div', 'kpi-card ' + (c.cls||''));
    card.innerHTML = `<div class="label">${c.label}</div><div class="value">${c.value}</div><div class="sub">${c.sub}</div>`;
    row.appendChild(card);
  });
})();

// ── Dead Code Table ───────────────────────────────────────────────────────────
(function() {
  const body = document.getElementById('dead-body');
  const count = document.getElementById('dead-count');
  const items = DEAD_CODE || [];
  count.textContent = items.length + ' item' + (items.length !== 1 ? 's' : '');
  if (!items.length) { body.innerHTML = '<div class="empty"><div class="icon">✓</div>No dead code detected</div>'; return; }
  const tbl = el('table');
  tbl.innerHTML = '<thead><tr><th>Kind</th><th>Name</th><th>Source File</th><th>Why Dead</th><th>Evidence</th></tr></thead>';
  const tbody = el('tbody');
  items.forEach(r => {
    const tr = el('tr', 'dead-row');
    const kindBadge = r.kind === 'explore' ? 'badge-red' : 'badge-orange';
    const pills = evidenceListHtml(r.evidence_ids);
    tr.innerHTML = `
      <td><span class="badge ${kindBadge}">${r.kind}</span></td>
      <td style="font-family:monospace;font-weight:600">${r.name}</td>
      <td class="file-tag">${r.source_file||''}</td>
      <td>${r.static_reason||''}<div class="reason-text">${r.usage_reason||''}</div></td>
      <td>${pills}</td>`;
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
  body.appendChild(tbl);
})();

// ── PDT Ledger ────────────────────────────────────────────────────────────────
(function() {
  const body = document.getElementById('pdt-body');
  const pdts = PDT_LEDGER || [];
  if (!pdts.length) { body.innerHTML = '<div class="empty"><div class="icon">✓</div>No PDTs detected</div>'; return; }

  const wrap = el('div', 'pdt-layout');

  // Chart
  const chartWrap = el('div');
  chartWrap.innerHTML = '<div class="chart-wrap"><canvas id="pdt-chart"></canvas></div>';
  wrap.appendChild(chartWrap);

  // Table
  const tableWrap = el('div');
  const tbl = el('table');
  tbl.innerHTML = '<thead><tr><th>PDT View</th><th>Cost / mo</th><th>Builds</th><th>Data Scanned</th><th>Status</th><th>Used By</th></tr></thead>';
  const tbody = el('tbody');
  pdts.forEach(r => {
    const tr = el('tr');
    const isUnused = r.status === 'unused';
    const isZombie = r.status === 'zombie';
    const statusCell = isZombie
      ? `<span class="zombie-badge">⚠ ZOMBIE — ${fmt_usd(r.estimated_cost_usd)}/mo</span>`
      : isUnused
      ? `<span class="kill-badge">⚠ KILL — ${fmt_usd(r.estimated_cost_usd)}/mo</span>`
      : `<span class="badge badge-green">In Use</span>`;
    const costColor = isZombie ? 'var(--purple)' : isUnused ? 'var(--red)' : 'var(--text)';
    const explores = (r.used_by_explores||[]).map(e => `<div class="file-tag">${e}</div>`).join('');
    tr.innerHTML = `
      <td style="font-family:monospace;font-weight:600">${r.view}</td>
      <td style="font-weight:600;color:${costColor}">${fmt_usd(r.estimated_cost_usd)}</td>
      <td>${r.build_count}</td>
      <td>${fmt_bytes(r.bytes_processed)}</td>
      <td>${statusCell}</td>
      <td>${explores || '<span style="color:var(--muted)">none</span>'}</td>`;
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
  tableWrap.appendChild(tbl);
  wrap.appendChild(tableWrap);
  body.appendChild(wrap);

  // Render chart after DOM is ready
  requestAnimationFrame(() => {
    const ctx = document.getElementById('pdt-chart');
    if (!ctx || typeof Chart === 'undefined') return;
    try { new Chart(ctx, {
      type: 'bar',
      data: {
        labels: pdts.map(r => r.view),
        datasets: [{
          label: 'Cost / mo (USD)',
          data: pdts.map(r => r.estimated_cost_usd),
          backgroundColor: pdts.map(r => r.status === 'zombie' ? 'rgba(155,89,182,0.7)' : r.status === 'unused' ? 'rgba(231,76,60,0.7)' : 'rgba(46,204,113,0.7)'),
          borderRadius: 4,
        }]
      },
      options: {
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: '#8892a4', callback: v => '$'+v }, grid: { color: '#2e3248' } },
          y: { ticks: { color: '#e2e8f0' }, grid: { display: false } },
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
    const evCount = (r.evidence_ids||[]).length;
    const li = el('li', 'roadmap-item');
    li.innerHTML = `
      <div class="roadmap-num">${i+1}</div>
      <div class="roadmap-body">
        <span class="badge ${cls}">${label}</span>
        &nbsp;<span class="roadmap-target">${escapeHtml(r.target)}</span>
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
  tbl.innerHTML = '<thead><tr><th>Kind</th><th>Table / Column</th><th>Field</th><th>Source File</th><th>Reason</th><th>Count</th></tr></thead>';
  const tbody = el('tbody');
  groups.forEach(r => {
    const tr = el('tr', 'dead-row');
    tr.innerHTML = `
      <td><span class="badge badge-red">${escapeHtml(r.kind)}</span></td>
      <td style="font-family:monospace">${escapeHtml(r.table||'')}${r.column ? ' · ' + escapeHtml(r.column) : ''}</td>
      <td class="file-tag">${escapeHtml(r.field||'')}</td>
      <td class="file-tag">${escapeHtml(r.source_file||'')}</td>
      <td class="reason-text">${escapeHtml(r.reason||'')}</td>
      <td>${r.count > 1 ? '×' + r.count : ''}</td>`;
    tbody.appendChild(tr);
  });
  tbl.appendChild(tbody);
  body.appendChild(tbl);
})();

// ── Migration Impact Accordion ────────────────────────────────────────────────
(function() {
  const body = document.getElementById('migration-body');
  const items = (MIGRATION||[]).filter(r => (r.explores||[]).length > 0);
  if (!items.length) { body.innerHTML = '<div class="empty"><div class="icon">—</div>No migration impact data</div>'; return; }
  items.forEach(r => {
    const item = el('div', 'accordion-item');
    const trigger = el('button', 'accordion-trigger');
    trigger.innerHTML = `<span class="arrow">▶</span><span style="font-family:monospace">${r.physical_table}</span><span style="margin-left:auto;font-size:12px;color:var(--muted)">${(r.explores||[]).length} explore${(r.explores||[]).length!==1?'s':''} affected</span>`;
    trigger.onclick = () => {
      const open = trigger.classList.toggle('open');
      content.classList.toggle('open', open);
    };
    const content = el('div', 'accordion-content');
    content.innerHTML = `<div class="impact-grid">
      <div class="impact-group"><label>Views</label><div class="items">${(r.views||[]).map(v=>`<span class="impact-tag">${v}</span>`).join('')||'<span style="color:var(--muted)">none</span>'}</div></div>
      <div class="impact-group"><label>Explores</label><div class="items">${(r.explores||[]).map(v=>`<span class="impact-tag">${v}</span>`).join('')}</div></div>
      <div class="impact-group"><label>Fields (${(r.fields||[]).length})</label><div class="items">${(r.fields||[]).slice(0,8).map(v=>`<span class="impact-tag">${v}</span>`).join('')}${(r.fields||[]).length>8?`<span style="color:var(--muted);font-size:11px">+${(r.fields||[]).length-8} more</span>`:''}</div></div>
    </div>`;
    item.appendChild(trigger);
    item.appendChild(content);
    body.appendChild(item);
  });
})();

// ── Cytoscape Dependency Graph ────────────────────────────────────────────────
(function() {
  const graphContainer = document.getElementById('cy');
  if (typeof cytoscape === 'undefined') {
    if (graphContainer) graphContainer.innerHTML = '<p style="color:#94a3b8;padding:24px">Graph library failed to load. Check your network connection.</p>';
    return;
  }
  if (!GRAPH_DATA || !GRAPH_DATA.nodes || GRAPH_DATA.nodes.length === 0) {
    if (graphContainer) graphContainer.innerHTML = '<p style="color:#94a3b8;padding:24px">No graph data — run <code>strata outputs --repo /path/to/lookml</code> to build the IR.</p>';
    return;
  }
  try {
    if (typeof cytoscapeDagre !== 'undefined') cytoscape.use(cytoscapeDagre);
  } catch(e) { /* dagre already registered */ }

  const cy = cytoscape({
    container: graphContainer,
    elements: [...GRAPH_DATA.nodes, ...GRAPH_DATA.edges],
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'label': 'data(label)',
          'color': '#e2e8f0',
          'font-size': '12px',
          'min-zoomed-font-size': 7,
          'text-valign': 'bottom',
          'text-margin-y': '4px',
          'text-outline-width': '2px',
          'text-outline-color': '#13151a',
          'width': 'data(size)',
          'height': 'data(size)',
          'shape': 'data(shape)',
          'border-width': 2,
          'border-color': 'rgba(255,255,255,0.08)',
        }
      },
      {
        selector: 'node:selected',
        style: { 'border-color': '#fff', 'border-width': 3 }
      },
      {
        selector: 'edge',
        style: {
          'line-color': 'data(color)',
          'target-arrow-color': 'data(color)',
          'target-arrow-shape': 'triangle',
          'arrow-scale': 0.7,
          'width': 1.5,
          'curve-style': 'bezier',
          'opacity': 0.7,
        }
      },
      {
        selector: 'edge[relation = "explore→joined_view"]',
        style: { 'line-style': 'dashed', 'line-dash-pattern': [6, 3] }
      },
      {
        selector: 'edge[relation = "view→physical_table"]',
        style: { 'line-style': 'dotted' }
      },
    ],
    layout: {
      name: 'dagre',
      rankDir: 'TB',
      nodeSep: 55,
      rankSep: 150,
      padding: 40,
      fit: true,
    },
    wheelSensitivity: 0.3,
  });
  CY = cy;

  const zoomIn = document.getElementById('cy-zoom-in');
  const zoomOut = document.getElementById('cy-zoom-out');
  const fitBtn = document.getElementById('cy-fit');
  const zoomAt = factor => cy.zoom({
    level: cy.zoom() * factor,
    renderedPosition: { x: graphContainer.clientWidth / 2, y: graphContainer.clientHeight / 2 },
  });
  if (zoomIn) zoomIn.addEventListener('click', () => zoomAt(1.25));
  if (zoomOut) zoomOut.addEventListener('click', () => zoomAt(1 / 1.25));
  if (fitBtn) fitBtn.addEventListener('click', () => cy.animate({ fit: { eles: cy.elements(), padding: 40 } }, { duration: 200 }));

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
  cy.on('tap', 'node', function(evt) {
    const d = evt.target.data();
    const rows = [];
    rows.push(detailRow('Name', `<span style="font-family:monospace;font-weight:600">${escapeHtml(d.label)}</span>`));
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
      rows.push(detailRow('Data Scanned', fmt_bytes(d.bytes_processed||0)));
      rows.push(detailRow('Used By', consumerListHtml(d.used_by_explores)));
    } else if (d.kind === 'view') {
      rows.push(detailRow('Referencing Explores', consumerListHtml(d.referencing_explores)));
    } else if (d.kind === 'physical_table') {
      const views = d.referencing_views || [];
      rows.push(detailRow('Referencing Views', `${views.length} view${views.length!==1?'s':''}`));
      if (views.length) {
        rows.push(detailRow('Views', views.map(v => `<span class="pill">${escapeHtml(v)}</span>`).join('')));
      }
    }

    rows.push(detailRow('Source File', `<span class="file-tag">${escapeHtml(d.source_file||'')}</span>`));
    panel.innerHTML = rows.join('');
  });

  cy.on('tap', function(evt) {
    if (evt.target === cy) panel.innerHTML = '<div class="detail-empty">Click a node to see details</div>';
  });
})();
</script>
</body>
</html>
"""
