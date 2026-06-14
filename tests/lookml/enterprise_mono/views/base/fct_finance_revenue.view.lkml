view: fct_finance_revenue {
  sql_table_name: `acme-analytics.gold_marts.fct_finance_revenue` ;;

  dimension: order_date {
    type: date
    sql: ${TABLE}.order_date ;;
    primary_key: yes
  }

  dimension: order_channel {
    type: string
    sql: ${TABLE}.order_channel ;;
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
    type: number
    sql: SAFE_DIVIDE(${shipping_margin}, NULLIF(${shipping_revenue}, 0)) ;;
    value_format_name: percent_2
  }
}
