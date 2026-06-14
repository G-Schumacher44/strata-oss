view: fct_cart_abandonment {
  sql_table_name: `acme-analytics.gold_marts.fct_cart_abandonment` ;;

  dimension: cart_date {
    type: date
    sql: ${TABLE}.cart_date ;;
    primary_key: yes
  }

  dimension: channel {
    type: string
    sql: ${TABLE}.channel ;;
  }

  measure: total_carts {
    type: sum
    sql: ${TABLE}.total_carts ;;
  }

  measure: abandoned_carts {
    type: sum
    sql: ${TABLE}.abandoned_carts ;;
  }

  measure: converted_carts {
    type: sum
    sql: ${TABLE}.converted_carts ;;
  }

  measure: conversion_rate {
    type: average
    sql: ${TABLE}.conversion_rate ;;
    value_format_name: percent_2
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

  measure: abandonment_rate {
    type: number
    sql: SAFE_DIVIDE(${abandoned_carts}, NULLIF(${total_carts}, 0)) ;;
    value_format_name: percent_2
  }
}
