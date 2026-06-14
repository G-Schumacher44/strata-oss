view: int_attributed_purchases {
  sql_table_name: `acme-analytics.silver.int_attributed_purchases` ;;

  dimension: order_id {
    type: string
    sql: ${TABLE}.order_id ;;
    primary_key: yes
  }

  dimension: order_dt {
    type: date
    sql: ${TABLE}.order_dt ;;
  }

  dimension: order_channel {
    type: string
    sql: ${TABLE}.order_channel ;;
  }

  dimension: customer_tier {
    type: string
    sql: ${TABLE}.customer_tier ;;
  }

  dimension: payment_method {
    type: string
    sql: ${TABLE}.payment_method ;;
  }

  dimension: is_expedited {
    type: yesno
    sql: ${TABLE}.is_expedited ;;
  }

  measure: order_count {
    type: count_distinct
    sql: ${TABLE}.order_id ;;
  }

  measure: gross_total {
    type: sum
    sql: ${TABLE}.gross_total ;;
    value_format_name: usd
  }

  measure: net_total {
    type: sum
    sql: ${TABLE}.net_total ;;
    value_format_name: usd
  }

  measure: total_discount_amount {
    type: sum
    sql: ${TABLE}.total_discount_amount ;;
    value_format_name: usd
  }

  measure: avg_order_value {
    type: average
    sql: ${TABLE}.gross_total ;;
    value_format_name: usd
  }
}
