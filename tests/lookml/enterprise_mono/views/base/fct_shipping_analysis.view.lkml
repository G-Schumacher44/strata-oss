view: fct_shipping_analysis {
  sql_table_name: `acme-analytics.gold_marts.fct_shipping_analysis` ;;

  dimension: order_date {
    type: date
    sql: ${TABLE}.order_date ;;
    primary_key: yes
  }

  dimension: order_channel {
    type: string
    sql: ${TABLE}.order_channel ;;
  }

  dimension: shipping_speed {
    type: string
    sql: ${TABLE}.shipping_speed ;;
  }

  measure: orders {
    type: sum
    sql: ${TABLE}.orders ;;
  }

  measure: shipping_revenue {
    type: sum
    sql: ${TABLE}.shipping_revenue ;;
    value_format_name: usd
  }

  measure: shipping_cost {
    type: sum
    sql: ${TABLE}.shipping_cost ;;
    value_format_name: usd
  }

  measure: shipping_margin {
    type: sum
    sql: ${TABLE}.shipping_margin ;;
    value_format_name: usd
  }

  measure: shipping_margin_pct {
    type: average
    sql: ${TABLE}.shipping_margin_pct ;;
    value_format_name: percent_2
  }

  measure: avg_shipping_cost_per_order {
    type: number
    sql: SAFE_DIVIDE(${shipping_cost}, NULLIF(${orders}, 0)) ;;
    value_format_name: usd
  }
}
