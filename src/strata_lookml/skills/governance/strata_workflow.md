# Strata Workflow Skill

A step-by-step guide for running the full Strata analysis pipeline. Intended for agents
that can execute shell commands and read JSON — no codebase knowledge required.

---

## Prerequisites

- Python virtualenv at `.venv/` (run `python -m venv .venv && pip install -e .` once)
- A LookML repo cloned locally (path = `<REPO_PATH>`)
- Optional: a usage facts JSON file (see §3 below)
- Optional: a schema facts JSON file (see §4 below)

---

## Step 1 — Run the CI suite

```bash
strata check \
  --repo tests/lookml/gcs_analytics \
  --usage-fixture tests/fixtures/gcs_usage_facts.json \
  --schema-fixture tests/fixtures/gcs_schema_facts.json
```

This runs in order:
1. `pytest` — unit + integration tests (must all pass)
2. `strata validate --check-replay` — Conductor spine + replay facts gate
3. `strata check` — scenario gates on gcs_analytics playground
4. `strata outputs` — writes 8 JSON artifacts to `output/gcs_analytics/`

If any step fails, stop and report the error. Do not proceed to the dashboard.

---

## Step 2 — View the dashboard

```bash
strata dashboard \
  --repo tests/lookml/gcs_analytics \
  --usage-fixture tests/fixtures/gcs_usage_facts.json \
  --schema-fixture tests/fixtures/gcs_schema_facts.json
```

Opens `http://localhost:8765/dashboard.html` in your browser. The dashboard is
self-contained HTML — you can also open `output/gcs_analytics/dashboard.html`
directly without the server.

If you get `OSError: [Errno 48] Address already in use`, kill the old server:
```bash
lsof -ti:8765 | xargs kill -9
strata dashboard ...
```

---

## Step 3 — Run against a different LookML repo

```bash
strata outputs \
  --repo <REPO_PATH> \
  --usage-fixture <USAGE_JSON> \
  --schema-fixture <SCHEMA_JSON> \
  --out output/<REPO_NAME>

strata dashboard \
  --repo <REPO_PATH> \
  --usage-fixture <USAGE_JSON> \
  --schema-fixture <SCHEMA_JSON>
```

Both `--usage-fixture` and `--schema-fixture` are optional. Without them, Strata
runs L0-only (structural analysis, no usage enrichment).

### Repo-agnostic config

Set `STRATA_REPO_PATH` in your shell or `~/.strata/config.json`:

```json
{ "repo_path": "/path/to/your/lookml" }
```

Then `strata check`, `strata outputs`, and `strata dashboard` all resolve your repo
automatically. See `strata mcp config` to verify resolution.

---

## Step 4 — Understand the output files

All artifacts land in `output/<repo-name>/`:

| File | What it tells you |
|---|---|
| `catalog.json` | Every model/explore/view/field/PDT/table in the repo |
| `dead_code_register.json` | Views + explores with zero usage (safe to deprecate) |
| `pdt_ledger.json` | Each PDT: build count, bytes, cost/period, used/unused |
| `cleanup_roadmap.json` | Prioritized action list (deprecate / kill PDT / repair schema) |
| `schema_drift.json` | IR references tables or columns absent from warehouse schema |
| `migration_impact.json` | Per physical table: which views and explores break if it changes |
| `validation_scope.json` | Minimal explore set to revalidate for a set of changed files |
| `usage_summary.json` | Counts: explores, queries, dead, PDTs, schema drift issues |

---

## Step 5 — Interpret the findings

**Dead code** (`dead_code_register.json`): safe to deprecate when `static_reason`
(structural orphan) AND `usage_reason` (zero queries) both present. Never act on
static-only signal — extends chains can make views look orphaned when they aren't.

**PDT cost** (`pdt_ledger.json`): `status: "unused"` + `estimated_cost_usd > 0` →
immediate kill candidate. Confirm with the explore team before deleting.

**Schema drift** (`schema_drift.json`): `missing_table` → LookML points at a table
that doesn't exist in the warehouse. `missing_column` → a field's SQL references a
column the warehouse doesn't have. Both are silent breakage; fix before the next deploy.

**Migration impact** (`migration_impact.json`): before touching a physical table,
check this file. It lists every view, explore, and field that will break.

---

## Usage Facts Format

If you have Looker System Activity data (or are building a fixture), the usage facts
JSON must follow this schema:

```json
{
  "period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "days": 30},
  "explore_usage": [
    {"model": "my_model", "explore": "my_explore", "query_count": 120, "last_queried_at": "2026-06-06T08:00:00Z"}
  ],
  "content_references": [
    {"content_id": "dashboard_42", "content_type": "dashboard", "model": "my_model", "explore": "my_explore", "title": "Sales Overview"}
  ],
  "pdt_builds": [
    {"view": "my_pdt", "build_count": 30, "last_built_at": "2026-06-06T04:00:00Z", "bytes_processed": 5200000000, "estimated_cost_usd": 28.0}
  ]
}
```

`period` is optional but strongly recommended — without it the dashboard shows
"period unknown" instead of "last 30 days".

---

## Schema Facts Format

```json
{
  "tables": [
    {"name": "project.dataset.table", "columns": ["col1", "col2", "col3"]}
  ]
}
```

Table names must match the `sql_table_name` values in your LookML (without backticks).

---

## Capability Tiers

Strata is offline-first. It gains additional abilities when external data is available,
but its core never makes HTTP calls.

| Tier | What you provide | What Strata adds |
|---|---|---|
| L0 only | LookML repo | Structural analysis, extends chain, orphans |
| + usage fixture | Usage JSON | Dead code register, PDT ledger, cleanup roadmap |
| + schema fixture | Schema JSON | Schema drift, migration impact |
| + BQ MCP | Agent fetches schema via bq_query → writes schema JSON | Same as above, but live |
| + Looker MCP | Agent fetches usage via Looker API → writes usage JSON | Same as above, but live |
| + Looker live | `make auth` + `.strata` with LOOKER_URL | Full live: usage + cost pulled directly from Looker system activity |

For BQ schema via MCP: query `INFORMATION_SCHEMA.COLUMNS` in your project, write
the result as schema facts JSON, pass with `--schema-fixture`.

---

## MCP Interactive Investigation

Strata runs as a stdio MCP server (`.mcp.json` in project root). Claude Code loads it
automatically. The MCP tools are read-only queries over the pre-built IR graph.

Start the server manually or via the project config:
```bash
strata mcp run                       # uses STRATA_REPO_PATH env var
STRATA_REPO_PATH=tests/lookml/gcs_analytics \
STRATA_USAGE_FIXTURE=tests/fixtures/gcs_usage_facts.json \
strata mcp run                       # switch playground via env
```

Validate before opening your AI client:
```bash
strata mcp validate
```

### Workflow 1 — Dead Code Audit

```
strata_ir_status          # confirm IR built, check explore/view counts
strata_usage_summary      # dead_code_count > 0 → proceed
strata_dead_code_register # full list: [explore] and [view] kinds
strata_explore_deps       # for each dead explore: verify joins before recommending removal
```

Both `static_reason` (structural orphan) AND `usage_reason` (zero queries) must be present
before flagging for removal. Extends chains can make views look orphaned — the dual-evidence
rule prevents false positives.

### Workflow 2 — PDT Cost Audit

```
strata_usage_summary  # pdt_count, unused_pdt_count
strata_pdt_costs      # sorted by cost; status="unused" or backed by dead explore = zombie
strata_impact         # for each zombie: which views/explores depend on its physical table
```

A zombie PDT is one that:
- Has `status: "unused"` (no explore references it), OR
- Is backed exclusively by explores in the dead code register

Cross-reference zombie PDT's `used_by_explores` list with `strata_dead_code_register`
output to confirm the backing explore has zero queries before recommending deletion.

enterprise_mono example: $63,750/30d → ~$765K/yr in zombie compute from 2 PDTs
(`pdt_attribution_full_funnel` backed by `dead_finance_v2`,
`pdt_customer_value_score` backed by `dead_orders_v2`).

### Workflow 3 — Schema Drift Review

```
strata_usage_summary  # schema_drift_count > 0 → proceed
strata_schema_drift   # list: missing_column (real drift) vs missing_table (often CTE FP)
strata_query_field    # for each missing_column hit: inspect field SQL to confirm column name
```

`missing_column` records are real drift — the field SQL references `${TABLE}.column_name`
but the warehouse schema doesn't have that column. These are silent breakage.

`missing_table` records are often CTE false positives — `_sql_upstreams()` regex matches
CTE names in PDT SQL. Check `source_file`: if it's a PDT with nested CTEs (like
`pdt_customer_value_score`), treat `missing_table` as a false positive.

### Workflow 4 — PR Impact / Validation Scope

```
strata_validation_scope(changed=["view:my_view", "explore:my_explore"])
# Returns: explores that must be revalidated before merging
strata_impact(physical_table="project.dataset.table")
# Returns: views, explores, fields that break if this table changes
```

Use `validation_scope` before merging a PR that touches LookML views. Use `impact` before
any warehouse schema migration (column drop, table rename, dataset reorganization).

---

## Available Playgrounds

Three reference repos in `tests/lookml/` with matching fixtures in `tests/fixtures/`:

| Playground | Models | Explores | Focus |
|---|---|---|---|
| `thelook` | 1 | 3 | Basic extends, dead explore, active PDT |
| `gcs_analytics` | 2 | 7 | Gold/silver layer, legacy explores, PDT cost |
| `enterprise_mono` | 19 | 34 | Cross-model extends, zombie PDTs ($765K/yr), 3 legacy connections, schema drift |

Run any playground:

```bash
# thelook
make ci REPO=tests/lookml/thelook USAGE=tests/fixtures/thelook_usage_facts.json

# gcs_analytics (default)
make ci

# enterprise_mono
make ci REPO=tests/lookml/enterprise_mono \
  USAGE=tests/fixtures/enterprise_usage_facts.json \
  SCHEMA=tests/fixtures/enterprise_schema_facts.json
```

The enterprise_mono playground demonstrates the G4 scenario: two PDTs
(`pdt_customer_value_score` + `pdt_attribution_full_funnel`) running at $63,750/month
backed only by explores with zero queries — $765K/year in zombie compute surfaced.
