view: pdt_sales_velocity {
  derived_table: {
    sql:
      SELECT
        s.product_id,
        s.order_date,
        s.sales_velocity_7d,
        s.trend_signal,
        s.inventory_risk_tier,
        s.gross_profit,
        s.net_margin,
        p.units_sold,
        p.gross_revenue AS product_revenue,
        p.margin_pct,
        i.product_name,
        i.category,
        i.locked_capital,
        i.attention_score
      FROM `acme-analytics.gold_marts.fct_sales_operations` s
      LEFT JOIN `acme-analytics.gold_marts.fct_product_profitability` p
        ON s.product_id = p.product_id AND s.order_date = p.product_date
      LEFT JOIN `acme-analytics.silver.int_inventory_risk` i
        ON s.product_id = i.product_id
      WHERE s.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    ;;
    persist_for: "8 hours"
  }

  dimension: product_id {
    type: string
    sql: ${TABLE}.product_id ;;
    primary_key: yes
  }

  dimension: order_date {
    type: date
    sql: ${TABLE}.order_date ;;
  }

  dimension: product_name {
    type: string
    sql: ${TABLE}.product_name ;;
  }

  dimension: category {
    type: string
    sql: ${TABLE}.category ;;
  }

  dimension: trend_signal {
    type: string
    sql: ${TABLE}.trend_signal ;;
  }

  dimension: inventory_risk_tier {
    type: string
    sql: ${TABLE}.inventory_risk_tier ;;
  }

  measure: avg_sales_velocity_7d {
    type: average
    sql: ${TABLE}.sales_velocity_7d ;;
    value_format_name: decimal_2
  }

  measure: total_gross_profit {
    type: sum
    sql: ${TABLE}.gross_profit ;;
    value_format_name: usd
  }

  measure: total_locked_capital {
    type: sum
    sql: ${TABLE}.locked_capital ;;
    value_format_name: usd
  }

  measure: avg_attention_score {
    type: average
    sql: ${TABLE}.attention_score ;;
    value_format_name: decimal_2
  }

  measure: product_count {
    type: count_distinct
    sql: ${TABLE}.product_id ;;
  }
}
