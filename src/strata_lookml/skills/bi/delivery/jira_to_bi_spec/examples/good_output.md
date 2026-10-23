# Output: jira_to_bi_spec

## BI Work Spec — DATA-204: Revenue dashboard for the new EMEA sales team

**Reporter:** Mike Chen (VP Sales)
**Priority:** P2
**Original ask:** "Revenue performance for EMEA — by country and product line, vs last year, quarterly view, filter by rep."

---

## Business Ask
Show EMEA revenue performance broken down by country and product line, with a year-over-year comparison and a quarterly time grain, filterable by sales rep.

## Data Sources
- `enterprise.orders` explore — confirmed live (1,204 queries last 30 days). Contains `total_revenue`, `created_date`, `country`, `product_line`, `sales_rep_name`.
- ⚠️ `enterprise.finance_overview` — also has revenue, but flagged: 0 queries last 30 days (dead code). Do not use.

## Definitions Needed
- **"Revenue"**: ambiguous — could mean `orders.total_revenue` (gross) or `orders.net_revenue` (after refunds). `[JUDGMENT REQUIRED]` — confirm with Mike which is the hero metric before building.
- **"EMEA"**: is this a filter on `country` (list of countries) or a `region` dimension? The `orders` explore has `customer_region` but no `EMEA` value confirmed in data — need to verify filter value.
- **"vs last year"**: YoY comparison — period-over-period calculated field or two separate tiles? Confirm preferred format.

## Assumptions
- Date range: current year + prior year for YoY (rolling 24 months)
- Grain: one row = one order, aggregated to quarterly
- Scope: EMEA region only (filter applied at explore level)

## Acceptance Criteria
- [ ] Revenue metric matches source-of-truth finance report for Q1 2026 within 0.1%
- [ ] Country breakdown covers all EMEA countries with at least 1 order
- [ ] YoY delta is visible per quarter (Q1 2026 vs Q1 2025)
- [ ] Sales rep filter works and does not break country breakdown
- [ ] Dashboard loads in < 5 seconds (PDT or cached explore)

## Technical Plan
1. `bq_schema_probe` on `acme-data.analytics.orders` — confirm `customer_region`, `product_line`, `sales_rep_name` column names
2. Confirm "Revenue" definition with Mike (gross vs net)
3. `dashboard_composer` with `audience: executive`, `explore: enterprise.orders`
4. Human review of filled config before `looker_mcp.create_dashboard`

## Open Questions
- **Blocking:** Gross or net revenue as the hero metric?
- **Blocking:** What values does `customer_region` use for EMEA? Need to confirm filter value(s).
- **Non-blocking:** Should "filter by rep" be a dashboard filter or a dimension on a tile?

## Suggested Next Skill
`bq_schema_probe` on `acme-data.analytics.orders` — confirm column names and EMEA region values before speccing the dashboard config.
