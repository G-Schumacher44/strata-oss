view: int_customer_lifetime_value {
  sql_table_name: `acme-analytics.silver.int_customer_lifetime_value` ;;

  dimension: customer_id {
    type: string
    sql: ${TABLE}.customer_id ;;
    primary_key: yes
  }

  dimension: customer_segment {
    type: string
    sql: ${TABLE}.customer_segment ;;
  }

  dimension: predicted_clv_bucket {
    type: string
    sql: ${TABLE}.predicted_clv_bucket ;;
  }

  dimension: actual_clv_bucket {
    type: string
    sql: ${TABLE}.actual_clv_bucket ;;
  }

  dimension: first_order_date {
    type: date
    sql: ${TABLE}.first_order_date ;;
  }

  dimension: last_order_date {
    type: date
    sql: ${TABLE}.last_order_date ;;
  }

  dimension: days_since_last_order {
    type: number
    sql: ${TABLE}.days_since_last_order ;;
  }

  dimension: ingest_dt {
    type: date
    sql: ${TABLE}.ingest_dt ;;
  }

  measure: total_customers {
    type: count_distinct
    sql: ${TABLE}.customer_id ;;
  }

  measure: total_spent {
    type: sum
    sql: ${TABLE}.total_spent ;;
    value_format_name: usd
  }

  measure: total_refunded {
    type: sum
    sql: ${TABLE}.total_refunded ;;
    value_format_name: usd
  }

  measure: net_clv {
    type: sum
    sql: ${TABLE}.net_clv ;;
    value_format_name: usd
  }

  measure: order_count {
    type: sum
    sql: ${TABLE}.order_count ;;
  }

  measure: return_count {
    type: sum
    sql: ${TABLE}.return_count ;;
  }

  measure: avg_order_value {
    type: average
    sql: ${TABLE}.avg_order_value ;;
    value_format_name: usd
  }
}
