# Input: bq_query_guardrail

**Context:** Agent has drafted SQL to answer "total orders by region last quarter"
and is about to execute it.

```
sql: |
  SELECT
    customer_region,
    COUNT(*) AS order_count,
    SUM(order_total_usd) AS revenue
  FROM `acme-data.analytics.orders`
  WHERE created_date BETWEEN '2026-01-01' AND '2026-03-31'
  GROUP BY customer_region
  ORDER BY revenue DESC

cost_threshold_gb: 100
bq_project: acme-data
```
