view: fct_customer_segments {
  sql_table_name: `acme-analytics.gold_marts.fct_customer_segments` ;;

  dimension: customer_segment {
    type: string
    sql: ${TABLE}.customer_segment ;;
    primary_key: yes
  }

  dimension: predicted_clv_bucket {
    type: string
    sql: ${TABLE}.predicted_clv_bucket ;;
  }

  dimension: actual_clv_bucket {
    type: string
    sql: ${TABLE}.actual_clv_bucket ;;
  }

  measure: customer_count {
    type: sum
    sql: ${TABLE}.customer_count ;;
  }

  measure: avg_net_clv {
    type: average
    sql: ${TABLE}.avg_net_clv ;;
    value_format_name: usd
  }

  measure: avg_order_value {
    type: average
    sql: ${TABLE}.avg_order_value ;;
    value_format_name: usd
  }

  measure: avg_total_spent {
    type: average
    sql: ${TABLE}.avg_total_spent ;;
    value_format_name: usd
  }

  measure: total_clv {
    type: sum
    sql: ${TABLE}.avg_net_clv * ${TABLE}.customer_count ;;
    value_format_name: usd
  }
}
