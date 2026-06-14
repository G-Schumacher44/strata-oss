# Outputs Layer

**Entry point:** `build_artifacts(graph)` and `write_artifacts(graph, out_dir)`

---

## What this layer is

Takes an enriched `IRGraph` (L0 + L1) and produces deterministic JSON artifacts and an
interactive HTML dashboard. No analysis happens here — it serializes what L0/L1 computed.

## Hard constraints

- **Deterministic.** Given the same `IRGraph`, output must be identical every run.
  No timestamps, no random ordering, no non-deterministic sets in output JSON.
- **No LLM calls.** Pure serialization and HTML templating.
- **No graph mutation.** This layer reads `graph` — it never modifies `metadata`.

## The 8 artifacts

`build_artifacts(graph)` returns a dict with these keys:

| Artifact | Source in graph.metadata |
|---|---|
| `catalog` | All IR nodes — views, explores, fields, PDTs, physical tables |
| `dead_code_register` | `l1.dead_code` — explores + zombie views with dual evidence |
| `pdt_ledger` | `l1.pdt_ledger` — PDT build cost, status, explore backers |
| `schema_drift` | `l1.schema_drift` — column-level drift hits |
| `usage_summary` | Aggregated counts from `l1` |
| `cleanup_roadmap` | Ranked remediation items from dead code + PDT ledger |
| `migration_impact` | View → physical table reverse mapping |
| `validation_scope` | Changed → impacted explore set (populated if `validation_scope_inputs` set) |

`write_artifacts(graph, out_dir)` calls `build_artifacts` then writes each to `out_dir/<name>.json`.

## Files

| File | Responsibility |
|---|---|
| `artifacts.py` | `build_artifacts()`, `write_artifacts()` — the 8 JSON outputs |
| `dashboard.py` | `build_dashboard_html()` — inlines artifact JSON + bundled JS into self-contained HTML |
| `notifications.py` | `build_slack_payload()`, `build_jira_tickets()` — notification payloads |
| `pr_report.py` | `build_pr_comment()` — markdown PR impact comment (used by StrataBot) |

## Dashboard

`build_dashboard_html()` inlines all 8 artifacts and 4 bundled JS libraries
(Cytoscape, Dagre, Chart.js) into a single self-contained HTML file. No CDN — renders
fully offline. JS lives in `src/strata/assets/js/`.
