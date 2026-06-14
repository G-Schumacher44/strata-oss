view: fct_sales_operations {
  sql_table_name: `acme-analytics.gold_marts.fct_sales_operations` ;;

  dimension: product_id {
    type: string
    sql: ${TABLE}.product_id ;;
    primary_key: yes
  }

  dimension: order_date {
    type: date
    sql: ${TABLE}.order_date ;;
  }

  dimension: trend_signal {
    type: string
    sql: ${TABLE}.trend_signal ;;
  }

  dimension: inventory_risk_tier {
    type: string
    sql: ${TABLE}.inventory_risk_tier ;;
  }

  measure: sales_velocity_7d {
    type: average
    sql: ${TABLE}.sales_velocity_7d ;;
    value_format_name: decimal_2
  }

  measure: total_inventory_quantity {
    type: sum
    sql: ${TABLE}.inventory_quantity ;;
  }

  measure: total_gross_profit {
    type: sum
    sql: ${TABLE}.gross_profit ;;
    value_format_name: usd
  }

  measure: avg_net_margin {
    type: average
    sql: ${TABLE}.net_margin ;;
    value_format_name: percent_2
  }

  measure: avg_return_rate {
    type: average
    sql: ${TABLE}.return_rate ;;
    value_format_name: percent_2
  }

  measure: product_count {
    type: count_distinct
    sql: ${TABLE}.product_id ;;
  }
}
