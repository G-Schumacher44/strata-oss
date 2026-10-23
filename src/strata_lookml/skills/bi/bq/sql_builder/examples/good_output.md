# Output: sql_builder

## SQL Draft — Weekly new user signups by acquisition channel (last 90 days)

**Tables:** `acme-data.analytics.users`
**Output shape:** time_series
**Date range:** DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) to CURRENT_DATE()
**Estimated cost:** 0.43 GB (~$0.00)
**Guardrail:** APPROVED

```sql
-- Weekly new user signups by acquisition channel — last 90 days
WITH signups AS (
  SELECT
    DATE_TRUNC(DATE(created_at), WEEK(MONDAY)) AS week_start,
    acquisition_channel,
    COUNT(*) AS new_users
  FROM `acme-data.analytics.users`
  WHERE DATE(created_at) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) AND CURRENT_DATE()
  GROUP BY week_start, acquisition_channel
)

SELECT
  week_start,
  acquisition_channel,
  new_users
FROM signups
ORDER BY week_start, new_users DESC
```

## Grain Assumptions
- `users`: one row = one user account — confirmed by grain_validator, no dedup needed

## Notes
- Used `WEEK(MONDAY)` for week truncation — change to `WEEK(SUNDAY)` if your reporting week starts Sunday
- `acquisition_channel` had 8% NULL in schema probe — NULLs will appear as a separate series labeled NULL; add `WHERE acquisition_channel IS NOT NULL` to exclude them if desired
- No JOIN required — single-table query, no fanout risk
