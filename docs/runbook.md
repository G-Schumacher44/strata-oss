# Strata — Governance Runbook

Operator playbook for running Strata governance investigations against a LookML repo.
Covers standard analysis, gate verification, findings format, and agentic delegation.

---

## Prerequisites

```bash
pip install -e ".[dev]"
strata mcp validate          # confirms repo path, IR cache, skills, token
```

Config resolution: `STRATA_REPO_PATH` env → `~/.strata/config.json` → cwd.
Run `strata mcp config` to see exactly what will be used.

---

## Standard Investigation

### 1 — Gate

Run before any investigation. Must pass before writing findings.

```bash
strata check \
  --repo /path/to/your/lookml \
  --usage-fixture /path/to/usage_facts.json \
  --schema-fixture /path/to/schema_facts.json
```

Against a playground:

```bash
strata check \
  --repo tests/lookml/enterprise_mono \
  --usage-fixture tests/fixtures/enterprise_usage_facts.json \
  --schema-fixture tests/fixtures/enterprise_schema_facts.json
```

### 2 — Build artifacts

```bash
strata outputs \
  --repo /path/to/your/lookml \
  --usage-fixture /path/to/usage_facts.json \
  --schema-fixture /path/to/schema_facts.json \
  --out output/my-repo
```

Writes 8 JSON files to `output/my-repo/` — see [CLI reference](./cli-guide.md#output-artifacts).

### 3 — Dashboard

```bash
strata dashboard \
  --repo /path/to/your/lookml \
  --usage-fixture /path/to/usage_facts.json \
  --schema-fixture /path/to/schema_facts.json
```

Opens `http://localhost:8765`. Self-contained HTML — also works by opening
`output/<repo-name>/dashboard.html` directly. Four panels: Overview, Dead Code
Register, PDT Ledger, Schema Drift.

---

## Workflow Patterns

### Dead Code Audit

Use for: scheduled cleanup, pre-migration, sprint kickoff.

**MCP tool sequence:**
```
strata_ir_status          → confirm IR built and explore count
strata_usage_summary      → dead_code_count, explore totals
strata_dead_code_register → full list with static + usage evidence
strata_explore_deps       → for each dead explore: verify joins
```

**Dual-evidence rule:** only flag for removal when both `static_reason` (structural orphan)
and `usage_reason` (zero queries) are present. Extends chains can make views look orphaned
when they aren't.

**Artifact:** `output/dead_code_register.json`

---

### PDT Cost Audit

Use for: cost reduction, quarterly review, any time BigQuery bills spike.

**MCP tool sequence:**
```
strata_usage_summary  → pdt_count, unused_pdt_count
strata_pdt_costs      → sorted by cost; status="unused" = zombie candidate
strata_impact         → which views/explores depend on the zombie's physical table
```

A zombie PDT is `status: "unused"` OR backed exclusively by explores in the dead code
register. Confirm with the explore team before deleting.

**Artifact:** `output/pdt_ledger.json`

**Reference numbers (enterprise_mono):** 2 zombie PDTs at $63,750/30d (~$765K/yr),
both backed by explores with zero queries.

---

### Schema Drift Review

Use for: post-migration validation, pre-deploy gate, after any warehouse rename or drop.

**MCP tool sequence:**
```
strata_usage_summary  → schema_drift_count > 0 → proceed
strata_schema_drift   → list by kind: missing_column (real) vs missing_table (possible CTE FP)
strata_query_field    → for each missing_column: inspect field SQL to confirm column name
```

`missing_column` = silent breakage — field SQL references `${TABLE}.column_name` but
column doesn't exist in warehouse. Fix before next deploy.

`missing_table` = often CTE false positives in PDT SQL. Check `source_file`: if it's a
PDT with nested CTEs, treat `missing_table` as a false positive.

**Artifact:** `output/schema_drift.json`

---

### PR Impact / Validation Scope

Use for: before merging any LookML PR, before any warehouse schema migration.

**MCP tool sequence:**
```
strata_validation_scope(changed=["view:my_view", "explore:my_explore"])
  → explores that must be revalidated before merging

strata_impact(physical_table="project.dataset.table")
  → views, explores, fields that break if this table changes
```

Run `strata validate` in CI to enforce the Conductor spine gate on every PR.

**Artifact:** `output/validation_scope.json`, `output/migration_impact.json`

---

## Findings Report Format

```markdown
## Strata Governance Report — [repo] — [date]

**Period:** [start] → [end] ([N]d)
**Gate:** PASS / FAIL

### Dead Code
[N] dead explores, [N] orphan views, [N] zombie views
- `model.explore_name` — 0 queries, backed by [PDT if applicable]

### PDT Costs
Total: $[X]/30d (~$[Y]/yr)
Zombie: $[X]/30d — [PDT names with backing explore]
Active: $[X]/30d

### Schema Drift
[N] real column drift hits, [N] false positives
- `view_name` → `table.column` — missing_column

### Recommended Actions
1. [Highest-cost zombie PDT] — delete after confirming explore is dead
2. [Dead explore cluster] — deprecate, remove after one sprint
3. [Schema drift views] — fix field SQL or update schema snapshot
```

---

## Stop Conditions

Stop immediately and report when:

- **Gate fails and root cause is outside task scope** — report the failure, stop. Do not widen scope without direction.
- **L0/L1 code would need an HTTP call** — design constraint violation. Stop and propose an alternative.
- **Unexpected repo state** — unfamiliar files, merge conflicts, broken imports not caused by your changes. Investigate; if unclear, stop and report.
- **Task brief is ambiguous on a consequential decision** — write a clarification question and stop.

---

## Agentic Delegation

Point an agent at the governance skills for autonomous runs:

```
skills/governance/strata_workflow.md        — step-by-step pipeline + MCP tool sequences
skills/governance/strata_agentic_runbook.md — agent execution rules + findings format
```

The agent reads the runbook on Turn 1, runs the gate, investigates, and writes a findings
report in the format above. Review asynchronously.

Live enrichment options for agents (opt-in, not required for CI):
- **BQ schema via MCP:** agent queries `INFORMATION_SCHEMA.COLUMNS` → writes schema JSON
- **Looker usage via Looker MCP:** agent fetches System Activity → writes usage JSON
- **Direct OAuth:** `strata auth login --looker-url <url>` → token at `~/.strata/tokens.json`

---

## Usage Facts Format

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
    {"view": "my_pdt", "build_count": 30, "last_built_at": "2026-06-06T04:00:00Z",
     "bytes_processed": 5200000000, "estimated_cost_usd": 28.0}
  ]
}
```

`period` is optional but strongly recommended — without it the dashboard shows "period unknown."

## Schema Facts Format

```json
{
  "tables": [
    {"name": "project.dataset.table", "columns": ["col1", "col2", "col3"]}
  ]
}
```

Table names must match `sql_table_name` values in your LookML (without backticks).

---

[← Strata README](../README.md) · [Docs index](./README.md)
