# Strata Testing Findings

Verified: 2026-06-06. All numbers sourced from actual output artifacts.

---

## Playground Matrix

| | thelook | gcs_analytics | enterprise_mono |
|---|---|---|---|
| **Purpose** | Parser + resolver baseline | L1 enrichment + drift | Enterprise stress test |
| **Models** | 1 | 3 | 19 |
| **Explores** | ~9 | 7 | 34 |
| **PDTs** | 0 | 2 | 5 |
| **Connection** | thelook | acme-analytics | acme-analytics + 2 legacy |
| **Cross-model extends** | No | No | Yes |
| **Schema fixtures** | No | Yes | Yes |
| **Legacy clusters** | No | No | Yes (3 decommissioned models) |
| **Zombie views** | Yes (1) | Yes (2) | Yes (5) |
| **Zombie PDTs** | No | No | Yes |

---

## CI Results — All Playgrounds

| Playground | Tests | validate.py | Scenario gates | Replay | Outputs |
|---|---|---|---|---|---|
| thelook | 44 / 44 ✅ | 10 / 10 ✅ | ✅ | ✅ | ✅ |
| gcs_analytics | 44 / 44 ✅ | 10 / 10 ✅ | ✅ | ✅ | ✅ |
| enterprise_mono | 44 / 44 ✅ | 10 / 10 ✅ | ✅ | ✅ | ✅ |

Period: 2026-05-07 → 2026-06-06 (30 days)

---

## L1 Findings — thelook

### Usage

| Metric | Value |
|---|---|
| Orphan views | 1 |
| Zombie views | 1 |
| Dead explores | 4 |
| Schema drift hits | 1 |

### Dead Code Register

| Item | Kind | Reason |
|---|---|---|
| `orphaned_campaigns` | view | no explore base / join / ancestor |
| `pdt_daily_revenue` | view | zombie — all referencing explores dead |
| `dead_revenue_report` | explore | 0 queries |
| `order_items_extended` | explore | 0 queries |
| `products` | explore | 0 queries |
| `users` | explore | 0 queries |

**Total dead code (thelook): 6** — 4 dead explores + 1 orphan view + 1 zombie view.

`pdt_daily_revenue` is a zombie view detected by the L1 zombie view pass (2026-06-06). Not previously surfaced because the orphan view check only catches views with no explore reference at all — `pdt_daily_revenue` was referenced by explores, but all those explores are dead.

### Schema Drift

| View | Table | Issue |
|---|---|---|
| (thelook views) | `analytics.marketing_campaigns` | missing_table — 2-part name, no BQ project; investigate mapping |

1 drift hit. `analytics.marketing_campaigns` is a 2-part physical table reference with no BQ project prefix in the LookML. The connection mapping is ambiguous without explicit `--bq-project`.

---

## L1 Findings — gcs_analytics

### Usage

| Metric | Value |
|---|---|
| Total queries (30d) | 1,975 |
| Active explores | 5 |
| Dead explores | 2 |
| Orphan views | 2 |
| Zombie views | 2 |
| Schema drift hits | 1 |

### Dead Code Register

| Item | Kind | Reason |
|---|---|---|
| `gcs_legacy.legacy_inventory` | explore | 0 queries |
| `gcs_legacy.legacy_orders` | explore | 0 queries |
| `orphaned_demand_forecast` | view | no explore base / join / ancestor |
| `pdt_retention_signals` | view | no explore / content usage |
| `silver_inventory` | view | zombie — all referencing explores dead |
| `silver_orders` | view | zombie — all referencing explores dead |

**Total dead code (gcs_analytics): 6** — 2 dead explores + 2 orphan views + 2 zombie views.

`silver_inventory` and `silver_orders` were invisible before the zombie view detection pass (2026-06-06). Both are referenced only by `gcs_legacy.legacy_inventory` and `gcs_legacy.legacy_orders` respectively — explores with 0 queries.

### PDT Ledger

| PDT | Builds/30d | Cost/30d | Status | Backed by |
|---|---|---|---|---|
| pdt_customer_ltv | 30 | $28.00 | active | gcs_analytics.customers |
| pdt_retention_signals | 30 | $156.00 | **unused** | (no explores) |
| **Total** | | **$184.00** | | |

`pdt_retention_signals` is structurally defined but no explore references it — dead view + running PDT.

---

## L1 Findings — enterprise_mono

### Usage

| Metric | Value |
|---|---|
| Total queries (30d) | 14,242 |
| Active explores | 28 |
| Dead explores | 6 |
| Zombie views | 5 |
| Schema drift hits (real) | 14 |
| Schema drift hits (CTE false positive) | 0 (fixed — CTE names stripped in `_sql_upstreams()`) |
| Models | 19 |
| Legacy/decommissioned models | 3 |

### Dead Explore Register

| Explore | Model | Connection | Reason |
|---|---|---|---|
| dead_finance_v2 | em_legacy_v2 | acme-analytics | 0 queries (zombie PDT backer) |
| dead_orders_v2 | em_legacy_v2 | acme-analytics | 0 queries (zombie PDT backer) |
| legacy_customers | em_legacy_v1 | legacy_redshift | decommissioned |
| legacy_inventory | em_legacy_v1 | legacy_redshift | decommissioned |
| legacy_orders | em_legacy_v1 | legacy_redshift | decommissioned |
| migration_orders | em_legacy_migration | legacy_warehouse_v1 | broken connection |

### PDT Ledger

| PDT | Builds/30d | Bytes | Cost/30d | Status | Backed by |
|---|---|---|---|---|---|
| pdt_attribution_full_funnel | 180 | 7.2 PB | **$45,000.00** | zombie | dead_finance_v2 |
| pdt_customer_value_score | 120 | 3.0 PB | **$18,750.00** | zombie | dead_orders_v2 |
| pdt_regional_kpi | 60 | 192 GB | $1.20 | active | 6 explores |
| pdt_sales_velocity | 90 | 504 GB | $3.15 | active | 3 explores |
| pdt_cohort_retention | 30 | 255 GB | $1.59 | active | customers_ds |

```
Zombie PDT cost (30d):  $63,750.00
Active PDT cost (30d):      $5.94
────────────────────────────────
Zombie annualized:     ~$765,000
```

Both zombie PDTs are backed exclusively by dead explores — the explore was never deleted, so the PDT keeps rebuilding on schedule.

### Zombie View Register

Views referenced exclusively by dead explores. Structurally connected to the IR but unreachable for any live query. Previously undetected (showed as "—" in risk coverage). Now surfaced via L1 zombie view pass added to `enrich.py`.

| View | Dead explores backing it | Notes |
|---|---|---|
| legacy_customer_profile | migration_orders, legacy_customers | 2 schema drift hits on dropped columns |
| legacy_inventory_snapshot | legacy_inventory | 2 schema drift hits on dropped columns |
| legacy_order_detail | migration_orders, legacy_orders | 1 schema drift hit |
| pdt_attribution_full_funnel | dead_finance_v2 | Also zombie PDT — $45,000/30d rebuild cost |
| pdt_customer_value_score | dead_orders_v2 | Also zombie PDT — $18,750/30d rebuild cost |

**Total dead code surface (enterprise_mono): 11 items** — 6 dead explores + 5 zombie views (3 legacy view files + 2 zombie PDTs cross-listed).

The zombie PDT views (`pdt_attribution_full_funnel`, `pdt_customer_value_score`) appear in both the PDT ledger (for cost context) and the dead code register (for removal action). The dead_code_register is the authoritative "remove this" list.

### Schema Drift — Real Hits (7)

| View | Table | Dropped Column | Fields Affected |
|---|---|---|---|
| legacy_order_detail | silver.int_attributed_purchases | unit_cost_usd | regional_gross_margin, total_unit_cost, unit_cost |
| legacy_customer_profile | silver.int_customer_retention_signals | customer_status_v1 | legacy_status |
| legacy_customer_profile | silver.int_customer_retention_signals | segment_score_v1 | segment_score |
| legacy_inventory_snapshot | silver.int_inventory_risk | reorder_threshold | reorder_threshold |
| legacy_inventory_snapshot | silver.int_inventory_risk | warehouse_zone | warehouse_zone |

### Schema Drift — Live BQ Ground Truth (2026-06-06)

`tests/fixtures/enterprise_schema_facts.json` replaced with a live pull from `acme-analytics` via `scripts/generate_schema_facts.py`. 173 columns across 12 tables.

**New hits vs hand-crafted fixture — `int_inventory_risk` migration (9 hits):**

| Column | Fields Affected | Notes |
|---|---|---|
| `attention_score` | `avg_attention_score` | dropped from real BQ |
| `ingest_dt` | `ingest_dt` | renamed to `ingestion_dt` in BQ, LookML not updated |
| `locked_capital` | `total_locked_capital` (×2) | dropped, affects `int_inventory_risk` + `legacy_inventory_snapshot` |
| `risk_tier` | `high_risk_product_count`, `risk_tier` (×3) | dropped, affects both views |
| `warehouse_zone` | `warehouse_zone` | pre-existing (also in legacy view) |

The hand-crafted fixture included these columns — the live pull reveals they were removed in a real schema migration that LookML was never updated to reflect. Seven silent failures that surface at query time, not at compile time.

**Total drift: 14** (3 from `int_attributed_purchases` + 2 from `int_customer_retention_signals` + 9 from `int_inventory_risk`)

### Schema Drift — CTE False Positives (fixed)

Previously: `clv_base`, `enriched`, `scored` from `pdt_customer_value_score` were flagged as `missing_table` because `_sql_upstreams()` matched `FROM cte_name` patterns inside `WITH` blocks.

**Fix (2026-06-06):** `_sql_upstreams()` now extracts CTE definitions (`\b(\w+)\s+AS\s*\(`) and subtracts them from upstream candidates before returning. False positives eliminated. Physical table count: 15 → 12 (CTE nodes no longer added to IR).

### Cross-Model Extends — Verified

| Extends chain | resolution_chain | Errors |
|---|---|---|
| customers_us (em_analytics_us) | `['customers', 'customers_us']` | 0 |
| finance_eu (em_analytics_eu) | `['finance', 'finance_eu']` | 0 |
| 32 other extends | correct | 0 |

34 explores across 19 models. 0 resolution errors. Extends chains resolve correctly via `rglob("*.lkml")` across all model files.

---

## Output Artifacts (per playground run)

| Artifact | Content |
|---|---|
| catalog.json | Full explore/view/field inventory |
| usage_summary.json | Query counts, dead/active totals, period metadata |
| dead_code_register.json | Dead explores + orphan views + zombie views with dual evidence |
| pdt_ledger.json | All PDTs, build counts, costs, explore backers, status |
| schema_drift.json | Missing column/table hits with field → table → source traceability |
| migration_impact.json | Blast radius per explore (fields, joins, content) |
| cleanup_roadmap.json | Prioritized cleanup steps with cost/risk labels |
| validation_scope.json | What was and wasn't validated, offline tier, fixture period |

8 artifacts per run. All deterministic — same fixtures produce identical output.

---

## Agentic Haiku Test — Schema Refresh Dry-Run

Haiku given: working dir, task description, pointer to `skills/strata_schema_refresh.md`. Instructed to run dry-run only and stop.

| Playground | Tokens | Tool Calls | Wall Time | Result |
|---|---|---|---|---|
| thelook | 13,273 | 2 | 6.2s | PASS — 1 physical table, 0 queryable (CTE-only), correctly identified as no-BQ-query scenario |
| gcs_analytics | 13,632 | 2 | 9.4s | PASS — 11 queryable, 2 datasets, stale fixture entries flagged |
| enterprise_mono | 13,581 | 2 | 10.7s | PASS — 12 queryable (CTE fix confirmed), 2 datasets, fixture complete |
| **Total (parallel)** | **~40,486** | **6** | **10.7s** | **3 / 3** |

When scoped to dry-run only, Haiku stays at ~13K tokens per run — on par with the CI benchmark. The previous 30K outlier was an unconstrained run that went on to read existing output files.

---

## Agentic Haiku Test

Haiku (`claude-haiku-4-5`) was given only: working directory, task description, and a pointer to the runbook. No step-by-step instructions embedded in the prompt.

| Playground | Tokens | Tool Calls | Wall Time | Result |
|---|---|---|---|---|
| gcs_analytics | 14,741 | 3 | 14s | PASS |
| thelook | 15,748 | 4 | 19s | PASS |
| enterprise_mono | 15,095 | 4 | 22s | PASS |
| **Total (parallel)** | **45,584** | **11** | **22s** | **3 / 3** |

Haiku read the runbook, self-navigated the CLI commands and fixture paths, and reported results correctly. The conductor docs are clear enough for the smallest model to operate autonomously.

**Token breakdown estimate per run:**
```
Runbook read:        ~3,000
strata check output: ~8,000
check_strata output: ~2,000
Response format:     ~2,000
─────────────────────────
Total per agent:    ~15,000
```

If runbook read is skipped (pure CI mode), ~12K tokens per playground is achievable.

---

## Risk Surface Coverage

| Risk | thelook | gcs_analytics | enterprise_mono |
|---|---|---|---|
| Parse + resolve (L0) | ✅ | ✅ | ✅ |
| Extends chain resolution | partial | partial | ✅ cross-model |
| Orphan view detection | ✅ (1) | ✅ (2) | — |
| Zombie view detection | ✅ (1) | ✅ (2) | ✅ (5) |
| Dead explore detection | — | ✅ | ✅ (6) |
| PDT cost tracking | — | ✅ | ✅ |
| Zombie PDT detection | — | partial | ✅ |
| Schema drift (column) | — | ✅ | ✅ (7 real) |
| Schema drift (CTE FP) | — | — | ✅ documented |
| Cross-model extends | — | — | ✅ |
| Legacy connection clusters | — | — | ✅ |
| Decommissioned model detection | — | — | ✅ |
| Multi-model namespace collision risk | — | — | ✅ |

---

## Known Gaps

| Gap | Status | Mitigation |
|---|---|---|
| CTE false positives in schema drift | documented | SQL AST parsing needed; 3 FPs clearly labeled `missing_table` not `missing_column` |
| Live Looker smoke | external gate pending | OAuth client registration + test instance URL required |
| `pdt_retention_signals` — unused flag vs. dead flag | correct behavior | PDT is defined but view has no explore backer; surfaces as unused PDT + dead view independently |
| thelook has no schema fixture | by design | thelook is a structural-only playground; L1 schema drift not exercised there |
| Zombie view detection gap | ✅ **fixed** | Views backed only by dead explores now surface in dead_code_register via `enrich.py` zombie view pass |
| CTE false positives in schema drift | ✅ **fixed** | `_sql_upstreams()` strips WITH-clause CTE names; 3 false positives eliminated, physical table count 15→12 |

---

[← Strata README](../README.md) · [Docs index](./README.md)
