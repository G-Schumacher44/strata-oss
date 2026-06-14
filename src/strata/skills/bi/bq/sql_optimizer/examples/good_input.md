# Input: sql_optimizer

**Context:** This query runs nightly as a PDT source. BQ job history shows
it scans 840 GB and takes 4 minutes. Analyst wants it under 50 GB.

```sql
sql: |
  SELECT DISTINCT
    u.user_id,
    u.acquisition_channel,
    u.created_at,
    COUNT(DISTINCT o.order_id) AS lifetime_orders,
    SUM(o.order_total_usd) AS lifetime_revenue
  FROM `acme-data.analytics.users` u
  JOIN `acme-data.analytics.orders` o ON u.user_id = o.user_id
  JOIN `acme-data.analytics.orders` o2 ON u.user_id = o2.user_id
  WHERE u.acquisition_channel NOT IN (
    SELECT acquisition_channel
    FROM `acme-data.analytics.blocked_channels`
  )
  GROUP BY u.user_id, u.acquisition_channel, u.created_at

execution_stats:
  bytes_processed: 902_341_120_000   # 840 GB
  slot_ms: 4_200_000
  wall_time_s: 247

bq_project: acme-data
```
