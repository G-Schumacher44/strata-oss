# Output: grain_validator

## Grain Validation — `acme-data.analytics.order_items`

**Candidate PK:** `order_item_id`
**Verdict:** CONFIRMED

**Row count:** 12,847,302
**Unique key count:** 12,847,302
**Duplicate rate:** 0.00%

## Grain Statement
One row = one line item within an order (a single SKU/quantity pair tied to an `order_id`).

## Duplicate Detail
None — table is unique at `order_item_id` level.

## JOIN Safety
- Safe to JOIN on `order_item_id` without aggregation: YES
- Joining `orders` to `order_items` on `order_id` will produce one row per line item
  (expected fan-out: orders → order_items is one-to-many). Aggregate at the
  `order_id` level after joining if you need order-level metrics.
