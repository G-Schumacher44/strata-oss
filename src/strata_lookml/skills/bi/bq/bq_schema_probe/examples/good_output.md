# Output: bq_schema_probe

## Tables Inspected
- `acme-data.analytics.orders` — 18 columns, partitioned on `created_date` (DAY)
- `acme-data.analytics.users` — 24 columns, partitioned on `created_at` (DAY)

## Grain Guess
- `orders`: one row = one order. Confidence: high (`order_id` is REQUIRED STRING, distinct in sample).
- `users`: one row = one user account. Confidence: high (`user_id` is REQUIRED STRING, distinct in sample).

## Candidate Primary Keys
- `orders.order_id` — REQUIRED STRING, matches table name pattern, no nulls in sample
- `users.user_id` — REQUIRED STRING, matches table name pattern, no nulls in sample

## Date Fields
- `orders.created_date` — DATE, range 2023-01-01 to 2026-06-05 (partition key)
- `orders.updated_at` — TIMESTAMP
- `users.created_at` — TIMESTAMP (partition key)
- `users.last_seen_at` — TIMESTAMP, 8% NULL in sample

## Join Candidates
- `orders.user_id` ↔ `users.user_id` — STRING / STRING, type match ✓
  Estimated cardinality: orders has ~4.2M rows, users has ~890K rows (many orders per user expected)

## Partition / Clustering
- `orders`: partition `created_date` DAY, clustering `customer_region, order_status`
- `users`: partition `created_at` DAY, clustering `acquisition_channel`

## Schema Drift Warnings
- `orders.customer_region` — 1 drift hit: column was renamed from `region` in the last 90 days.
  BQ has the new name; any LookML field referencing `${TABLE}.region` will error.

## Risk Notes
- `users.last_seen_at` 8% NULL — filter or COALESCE before using in a date range join
- `orders` is 18 columns — consider selecting only needed columns to reduce scan cost
