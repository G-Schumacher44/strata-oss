# Output: lookml_explore_join_reviewer

## Explore Join Review — `enterprise.orders_extended`

**Base view:** orders
**Joins:** 5
**Field count:** 142
**Dead code flag:** NO — 1,204 queries last 30 days

## Findings

### HIGH RISK
- [ ] Join `order_adjustments`: missing `relationship:` declaration — fanout type unknown. An untyped join defaults to `many_to_many` behavior in Looker, which will silently inflate `orders.total_revenue` whenever `order_adjustments` rows > 1 per order.

### FANOUT RISK
- [ ] Join `promotions`: `many_to_one` declared but no `fields:` constraint — all 34 promotion fields are exposed in the explore. If analysts select both `promotions.promo_type` and `orders.total_revenue` without understanding the join, results will fan out. Recommend adding `fields: [promotions.promo_type, promotions.discount_pct]` to limit exposure.

### DEAD JOINS
- [ ] Join `legacy_fulfillment`: view `legacy_fulfillment` has 0 fields in this explore's `fields:` list — join fires on every query but returns no usable fields. Remove or add a `fields:` list.

### OK
- [x] Join `customers`: `relationship: many_to_one` declared, `fields: [customers.region, customers.tier]` scoped correctly
- [x] Join `products`: `relationship: many_to_one` declared, full field list appropriate for an analytical explore

## Verdict
**NEEDS REVIEW**

## Recommended Actions
1. Add `relationship: many_to_one` to the `order_adjustments` join (confirm cardinality with data owner first — if one order can have multiple adjustments, this is `one_to_many` and the explore design needs rethinking)
2. Add `fields:` constraint to `promotions` join to limit exposure
3. Remove `legacy_fulfillment` join or add a `fields:` list — dead join adds query overhead with no value
