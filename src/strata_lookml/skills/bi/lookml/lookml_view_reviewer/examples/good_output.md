# Output: lookml_view_reviewer

## View Review — `finance_orders`

**Source:** `views/finance_orders.view.lkml`
**Table:** `acme-data.analytics.orders`
**Extends:** none
**Explores referencing this view:** `finance_overview` (892 queries/30d), `finance_debug` (0 queries — dead)
**Dead code flag:** NO (via live explore)

## Findings

### HIGH RISK
- [ ] Field `customer_region` (dimension): SQL is `${TABLE}.region` — column `region` no longer exists in BQ (renamed to `customer_region` 3 days ago). **This field will error at query time.** Fix: change SQL to `${TABLE}.customer_region`.
- [ ] Field `legacy_customer_id` (dimension): SQL is `${TABLE}.legacy_customer_id` — column dropped from BQ 14 days ago. This field will error at query time. Fix: remove field or replace with `${TABLE}.customer_id`.
- [ ] No `primary_key: yes` declared on any dimension — Looker cannot enforce join uniqueness. `order_id` is the natural PK candidate; add `primary_key: yes` to that dimension.

### UNBOUNDED MEASURES
- [ ] `gross_margin_v1` (measure, type: sum): SQL references `${TABLE}.gross_margin_v1` — column dropped from BQ. Will error at query time. Remove or replace with `${TABLE}.gross_margin`.

### OK
- [x] `total_revenue` (measure): SQL `${TABLE}.order_total_usd` — column confirmed present in BQ
- [x] `created_date` (dimension_group): `${TABLE}.created_date` — confirmed DATE column, partition key
- [x] All other sql: fields use `${TABLE}` substitution correctly
- [x] No liquid template injection detected

## Verdict
**HIGH RISK — 3 fields will error at query time. Do not deploy additional changes until these are fixed.**

## Recommended Actions
1. Fix `customer_region.sql`: `${TABLE}.region` → `${TABLE}.customer_region`
2. Remove `legacy_customer_id` dimension (or map to `customer_id` if still needed)
3. Remove or fix `gross_margin_v1` measure (column dropped from BQ)
4. Add `primary_key: yes` to `order_id` dimension
