view: fct_product_profitability {
  sql_table_name: `acme-analytics.gold_marts.fct_product_profitability` ;;

  dimension: product_id {
    type: string
    sql: ${TABLE}.product_id ;;
    primary_key: yes
  }

  dimension: product_date {
    type: date
    sql: ${TABLE}.product_date ;;
  }

  measure: units_sold {
    type: sum
    sql: ${TABLE}.units_sold ;;
  }

  measure: units_returned {
    type: sum
    sql: ${TABLE}.units_returned ;;
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

  measure: gross_profit {
    type: sum
    sql: ${TABLE}.gross_profit ;;
    value_format_name: usd
  }

  measure: net_margin {
    type: average
    sql: ${TABLE}.net_margin ;;
    value_format_name: percent_2
  }

  measure: return_rate {
    type: average
    sql: ${TABLE}.return_rate ;;
    value_format_name: percent_2
  }

  measure: margin_pct {
    type: average
    sql: ${TABLE}.margin_pct ;;
    value_format_name: percent_2
  }

  measure: product_count {
    type: count_distinct
    sql: ${TABLE}.product_id ;;
  }
}
