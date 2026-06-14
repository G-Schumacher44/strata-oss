# Output: semantic_layer_audit

## Semantic Layer Audit — enterprise_mono (2026-06-07)

**Model scope:** all models (enterprise, finance, marketing)
**IR built at:** 2026-06-07 06:12 UTC (5h ago — fresh)
**L1 data:** available (usage data current to 2026-06-06)

---

## Risk Surface

| Area | Count | Severity |
|---|---|---|
| Dead explores | 6 (35% of 17 total) | HIGH |
| Zombie views | 11 | HIGH |
| Schema drift hits | 23 (8 views affected) | HIGH |
| Unused PDTs | 4 (~$2,100/mo estimated build cost) | MEDIUM |
| Orphaned views | 14 | LOW |
| Orphaned fields | 47 | LOW |

---

## Top Findings

### CRITICAL
- [ ] **Dead explore rate is 35%** — 6 of 17 explores have 0 queries in 30 days. Semantic layer is significantly overgrown. Cleanup will reduce query routing confusion and PDT build cost.

### HIGH
- [ ] **`finance_orders` view — 9 drift hits** (above threshold of 5). Backs live explore `finance_overview` (892 queries/30d). Columns `region`, `legacy_customer_id`, `gross_margin_v1` no longer exist in BQ — queries against fields referencing these will fail at runtime.
- [ ] **`migration_orders` explore — dead (0 queries, zombie PDT)** — `pdt_migration_orders_daily` builds nightly, costs ~$63,750/mo in slot time. No users. Safe to retire.
- [ ] **`legacy_customers` explore — dead (0 queries)** — 3 zombie views depend on it. Removal candidate.

### MEDIUM
- [ ] `pdt_finance_daily_summary` — last queried 47 days ago. Build cost ~$890/mo. Evaluate for removal.
- [ ] `pdt_marketing_attribution` — last queried 61 days ago. Build cost ~$420/mo.

---

## Remediation Backlog

1. **`finance_orders` view** — 9 drift hits, backs live explore. Run `lookml_view_reviewer` immediately. Fix broken field SQL before next production deploy.
2. **`migration_orders` explore** — retire. Run `lookml_explore_join_reviewer` to confirm no hidden live dependencies, then remove explore + PDT. Estimated $63,750/mo savings.
3. **`legacy_customers` explore** — retire. 3 zombie views can be archived together.
4. **Remaining 4 dead explores** — `strata_dead_code_register` full list. Run `lookml_explore_join_reviewer` on each before removing.
5. **Unused PDTs** — `pdt_finance_daily_summary`, `pdt_marketing_attribution`, 2 others. Confirm no downstream usage, then drop.
6. **14 orphaned views** — low priority. Batch review and archive.

---

## Suggested Next Skills
- `lookml_view_reviewer` on: `finance_orders` (urgent — live explore + high drift)
- `lookml_explore_join_reviewer` on: `migration_orders`, `legacy_customers`
- `bq_schema_probe` on: `acme-data.analytics.orders` (confirm current column names to fix drift)
