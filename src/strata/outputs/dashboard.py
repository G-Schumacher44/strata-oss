"""Generate a self-contained HTML observability dashboard from Strata artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strata.ir.types import IRGraph
from strata.l1.enrich import evidence_facts, view_consumer_map

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


def _read_js(filename: str) -> str:
    js_dir = Path(__file__).resolve().parent.parent / "assets" / "js"
    return (js_dir / filename).read_text(encoding="utf-8")


def _build_l1_facts(graph: IRGraph) -> dict[str, Any]:
    """Serializes the raw L1 facts the evidence-sentence panel needs, keyed to match the
    `usage:`/`pdt_build:`/`schema_table:` evidence-id suffixes so the JS looks numbers up
    rather than re-deriving them (the panel-vs-canonical-source drift PR #25's review
    rounds kept catching). Aggregation (content-ref counts, column-count derivation) lives
    in `l1.enrich.evidence_facts()` — this function only reshapes what L1 already computed
    (per outputs/AGENTS.md: outputs serialize, they do not derive)."""
    l1 = graph.metadata.get("l1", {})
    facts = evidence_facts(graph)
    content_ref_counts = facts["content_reference_counts"]

    usage = {
        f"explore:{key}": {
            "query_count": rec["query_count"],
            "content_reference_count": content_ref_counts.get(key, 0),
        }
        for key, rec in l1.get("explore_usage", {}).items()
    }
    # A dead-explore verdict rests on two facts: zero queries AND zero content references
    # in the window. Live System Activity emits NO row for a never-queried explore, so a
    # usage-keyed comprehension alone drops exactly the explores whose verdicts most need
    # evidence — their chips fell to the "no usage row" fallback, substantiating neither
    # condition. Every explore node gets an entry; row absence itself is the zero-usage
    # fact (flagged so the sentence can say so instead of implying a serialized row).
    for node in graph.nodes.values():
        if node.kind != "explore":
            continue
        key = f"{node.attrs.get('model', '')}.{node.name}"
        usage.setdefault(
            f"explore:{key}",
            {
                "query_count": 0,
                "content_reference_count": content_ref_counts.get(key, 0),
                "no_usage_row": True,
            },
        )

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
    catalog = json.dumps(artifacts.get("catalog", []))
    dead_code = json.dumps(artifacts.get("dead_code_register", []))
    pdt_ledger = json.dumps(artifacts.get("pdt_ledger", []))
    roadmap = json.dumps(artifacts.get("cleanup_roadmap", []))
    schema_drift = json.dumps(artifacts.get("schema_drift", []))
    usage_summary = json.dumps(artifacts.get("usage_summary") or {})
    migration = json.dumps(artifacts.get("migration_impact", []))
    graph_json = json.dumps(graph_data)
    l1_facts = json.dumps(_build_l1_facts(graph))
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
a.ev-chip { cursor: pointer; border: 1px solid transparent; text-decoration: none; }
a.pill-link:hover { background: rgba(52,152,219,.2); color: var(--blue); border-color: var(--blue); }
a.pill-info:hover { background: rgba(136,146,164,.25); color: var(--text); border-color: var(--muted); }
a.row-primary-link { display: inline-block; padding: 0; border: none; background: none; color: inherit; font: inherit; margin: 0; }
a.row-primary-link:hover { color: var(--blue); background: none; }
.copy-link-btn { border: none; background: none; color: var(--muted); cursor: pointer; font-size: 11px; margin-left: 6px; padding: 0; vertical-align: middle; }
.copy-link-btn:hover { color: var(--blue); }
.evidence-sentence { display: block; font-size: 12px; color: var(--text); background: rgba(52,152,219,.08); border: 1px solid var(--border); border-radius: 6px; padding: 8px 10px; margin: 4px 0 8px; max-width: 520px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
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
const NODE_BY_ID = {};
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
function periodPhrase() {
  const p = L1_FACTS.period || {};
  if (!p.start || !p.end) return 'an unknown window';
  const days = p.days != null ? `${p.days}-day ` : '';
  return `the last ${days}window (${p.start} \u2192 ${p.end})`;
}
function exploreUsageSentence(modelDotName, sourceFile) {
  const fact = L1_FACTS.usage['explore:' + modelDotName];
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
  let s = `built ${buildCount || 0} time${buildCount !== 1 ? 's' : ''}, processing ${fmt_bytes(bytesProcessed || 0)} \u00b7 ${fmt_usd(costUsd || 0)} estimated over ${periodPhrase()}`;
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
      const fact = L1_FACTS.pdt_build[view];
      if (!fact) return `No PDT build facts were provided for '${view}'.`;
      const node = NODE_BY_ID['pdt:' + view];
      return pdtCostSentence(
        fact.build_count, fact.bytes_processed, fact.estimated_cost_usd,
        node ? node.used_by_explores : null, node ? node.source_file : null
      );
    }
    case 'schema_table': {
      const table = evId.slice('schema_table:'.length);
      const fact = L1_FACTS.schema_table[table];
      if (!fact) {
        return `table '${table}' was not found in the provided schema facts \u2014 the resolved IR references it, but no warehouse metadata confirms it exists.`;
      }
      const cols = fact.columns || [];
      const colList = cols.length ? `: ${cols.join(', ')}` : '';
      return `table '${table}' is present in the provided schema facts with ${fact.column_count} known column${fact.column_count !== 1 ? 's' : ''}${colList}.`;
    }
    case 'physical_table': {
      const table = evId.slice('physical_table:'.length);
      const fact = L1_FACTS.schema_table[table];
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
  const row = document.getElementById(id);
  if (!row) return;
  row.scrollIntoView({ behavior: 'smooth', block: 'center' });
  // Plain string equality on dataset — no selector-escaping regex. The escaped-regex
  // version died at parse time in the GENERATED page (non-raw Python string collapsed a
  // backslash layer: /["\]/g → unterminated class), killing every script on the page.
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
    const url = location.href.split('#')[0] + '#' + id;
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
    tr.id = r.id;
    const kindBadge = r.kind === 'explore' ? 'badge-red' : 'badge-orange';
    const pills = evidenceListHtml(r.evidence_ids);
    tr.innerHTML = `
      <td><span class="badge ${kindBadge}">${r.kind}</span></td>
      <td style="font-family:monospace;font-weight:600">${primaryChipHtml(r.id, r.name)}</td>
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
    const primaryId = 'pdt:' + r.view;
    tr.id = primaryId;
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
      <td style="font-family:monospace;font-weight:600">${primaryChipHtml(primaryId, r.view)}</td>
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
  const roadmapIdCounts = {};
  items.forEach((r, i) => {
    const [cls, label] = actionStyle[r.action] || ['badge-gray', r.action];
    const cost = r.estimated_cost_usd ? ` · saves ${fmt_usd(r.estimated_cost_usd)}/mo` : '';
    const evCount = (r.evidence_ids||[]).length;
    // Roadmap items carry no own artifact id — the chip itself resolves via the slice's own
    // evidence_ids[0] (explore:/view:/pdt:/field:, always the record's own namespace per
    // _cleanup_roadmap()) verbatim, unchanged. The DOM anchor/copy-link target is a SEPARATE
    // 'roadmap:' namespace so it can never collide with a ledger/register row's own id —
    // multiple actions can share one primaryId (e.g. two roadmap rows on the same field),
    // so a ':2'/':3' suffix disambiguates within the roadmap itself.
    const primaryId = r.evidence_ids[0];
    let roadmapId = 'roadmap:' + primaryId;
    const seen = (roadmapIdCounts[roadmapId] || 0) + 1;
    roadmapIdCounts[roadmapId] = seen;
    if (seen > 1) roadmapId += ':' + seen;
    const li = el('li', 'roadmap-item');
    li.id = roadmapId;
    li.innerHTML = `
      <div class="roadmap-num">${i+1}</div>
      <div class="roadmap-body">
        <span class="badge ${cls}">${label}</span>
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
    // Row's own SchemaDriftRecord id is the stable DOM anchor/copy-link target (several
    // rows can share one table, so `schema_table:` alone isn't unique enough for that);
    // the chip itself still resolves via `schema_table:`, one of the row's own
    // pre-existing evidence_ids (no new id scheme invented).
    tr.id = r.id;
    const chipLabel = (r.table||'') + (r.column ? ' · ' + r.column : '');
    tr.innerHTML = `
      <td><span class="badge badge-red">${escapeHtml(r.kind)}</span></td>
      <td style="font-family:monospace">${primaryChipHtml('schema_table:' + r.table, chipLabel, r.id)}</td>
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
