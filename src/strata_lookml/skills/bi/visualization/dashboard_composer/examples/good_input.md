# Input: dashboard_composer

**Context:** `jira_to_bi_spec` processed DATA-204. Open questions resolved:
revenue = net_revenue, EMEA = customer_region IN ('UK', 'DE', 'FR', 'NL', 'ES', 'IT').

```
business_ask: "EMEA revenue performance by country and product line, YoY, quarterly, filterable by sales rep"
audience: executive
explore: orders
model: enterprise
primary_metric: orders.net_revenue
```
