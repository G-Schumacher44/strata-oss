view: fct_daily_dashboard {
  sql_table_name: `acme-analytics.gold_marts.fct_daily_dashboard` ;;

  dimension: metric_date {
    type: date
    sql: ${TABLE}.metric_date ;;
    primary_key: yes
  }

  dimension: revenue_anomaly_flag {
    type: yesno
    sql: ${TABLE}.revenue_anomaly_flag ;;
  }

  measure: orders_count {
    type: sum
    sql: ${TABLE}.orders_count ;;
  }

  measure: gross_revenue {
    type: sum
    sql: ${TABLE}.gross_revenue ;;
    value_format_name: usd
  }

  measure: net_revenue {
    type: sum
    sql: ${TABLE}.net_revenue ;;
    value_format_name: usd
  }

  measure: avg_order_value {
    type: average
    sql: ${TABLE}.avg_order_value ;;
    value_format_name: usd
  }

  measure: carts_created {
    type: sum
    sql: ${TABLE}.carts_created ;;
  }

  measure: cart_conversion_rate {
    type: average
    sql: ${TABLE}.cart_conversion_rate ;;
    value_format_name: percent_2
  }

  measure: returns_count {
    type: sum
    sql: ${TABLE}.returns_count ;;
  }

  measure: return_rate {
    type: average
    sql: ${TABLE}.return_rate ;;
    value_format_name: percent_2
  }

  measure: refund_total {
    type: sum
    sql: ${TABLE}.refund_total ;;
    value_format_name: usd
  }

  measure: revenue_7d_avg {
    type: average
    sql: ${TABLE}.revenue_7d_avg ;;
    value_format_name: usd
  }

  measure: revenue_30d_avg {
    type: average
    sql: ${TABLE}.revenue_30d_avg ;;
    value_format_name: usd
  }

  measure: anomaly_day_count {
    type: count_distinct
    sql: CASE WHEN ${TABLE}.revenue_anomaly_flag THEN ${TABLE}.metric_date END ;;
  }
}
