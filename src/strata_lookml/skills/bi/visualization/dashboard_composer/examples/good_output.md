# Output: dashboard_composer

## Dashboard Plan

**Template:** executive_kpi_v1
**Explore:** enterprise.orders
**Audience:** Executive

### Filled Config

```yaml
dashboard:
  title: "EMEA Revenue Performance"
  explore: enterprise.orders
  filters:
    - field: orders.customer_region
      value: "UK,DE,FR,NL,ES,IT"
      ui_config:
        type: tag_list
    - field: orders.sales_rep_name
      value: ""
      ui_config:
        type: dropdown_menu
    - field: orders.created_date
      value: "this quarter"
      ui_config:
        type: relative_timeframes

tiles:
  - title: "Net Revenue (This Quarter)"
    type: single_value
    measure: orders.net_revenue
    comparison_type: previous_period
    comparison_label: "vs Last Quarter"

  - title: "Net Revenue by Quarter (YoY)"
    type: line
    dimension: orders.created_quarter
    measure: orders.net_revenue
    pivot: orders.created_year

  - title: "Net Revenue by Country"
    type: bar
    dimension: orders.country
    measure: orders.net_revenue
    sorts: [orders.net_revenue desc]
    limit: 10

  - title: "Net Revenue by Product Line"
    type: bar
    dimension: orders.product_line
    measure: orders.net_revenue
    sorts: [orders.net_revenue desc]
```

### Field Mapping

| Template slot | Field used | Why |
|---|---|---|
| primary_kpi.measure | orders.net_revenue | Confirmed as hero metric (DATA-204 spec) |
| trend.time_dimension | orders.created_quarter | Quarterly grain requested by stakeholder |
| breakdown.dimension | orders.country | First breakdown requested |
| secondary_breakdown | orders.product_line | Second breakdown requested |
| rep_filter | orders.sales_rep_name | Explicitly requested in comments |

### Fields Left as OPTIONAL (omitted)
- `secondary_kpi`: no second metric identified — only revenue was requested
- `goal_line`: no revenue target data available in this explore

### Ready to create?
Respond YES to call `looker_mcp.create_dashboard` with this config.

**Note:** The YoY tile uses `pivot: orders.created_year` — confirm that `created_year` is a dimension in the `enterprise.orders` explore. If not, use `created_date` with a date_start/date_end filter for the comparison period instead.
