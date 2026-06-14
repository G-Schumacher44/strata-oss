view: fct_marketing_attribution {
  sql_table_name: `acme-analytics.gold_marts.fct_marketing_attribution` ;;

  dimension: metric_date {
    type: date
    sql: ${TABLE}.metric_date ;;
    primary_key: yes
  }

  dimension: channel {
    type: string
    sql: ${TABLE}.channel ;;
  }

  measure: recovered_orders {
    type: sum
    sql: ${TABLE}.recovered_orders ;;
  }

  measure: total_orders {
    type: sum
    sql: ${TABLE}.total_orders ;;
  }

  measure: abandoned_carts {
    type: sum
    sql: ${TABLE}.abandoned_carts ;;
  }

  measure: converted_carts {
    type: sum
    sql: ${TABLE}.converted_carts ;;
  }

  measure: abandoned_value {
    type: sum
    sql: ${TABLE}.abandoned_value ;;
    value_format_name: usd
  }

  measure: avg_time_to_purchase_hours {
    type: average
    sql: ${TABLE}.avg_time_to_purchase_hours ;;
    value_format_name: decimal_1
  }

  measure: at_risk_customers {
    type: sum
    sql: ${TABLE}.at_risk_customers ;;
  }

  measure: total_customers {
    type: sum
    sql: ${TABLE}.total_customers ;;
  }

  measure: cart_recovery_rate {
    type: number
    sql: SAFE_DIVIDE(${recovered_orders}, NULLIF(${abandoned_carts}, 0)) ;;
    value_format_name: percent_2
  }
}
