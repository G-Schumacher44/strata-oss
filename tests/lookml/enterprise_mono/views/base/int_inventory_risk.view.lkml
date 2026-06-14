view: int_inventory_risk {
  sql_table_name: `acme-analytics.silver.int_inventory_risk` ;;

  dimension: product_id {
    type: string
    sql: ${TABLE}.product_id ;;
    primary_key: yes
  }

  dimension: product_name {
    type: string
    sql: ${TABLE}.product_name ;;
  }

  dimension: category {
    type: string
    sql: ${TABLE}.category ;;
  }

  dimension: risk_tier {
    type: string
    sql: ${TABLE}.risk_tier ;;
  }

  dimension: ingest_dt {
    type: date
    sql: ${TABLE}.ingest_dt ;;
  }

  measure: unit_price {
    type: average
    sql: ${TABLE}.unit_price ;;
    value_format_name: usd
  }

  measure: cost_price {
    type: average
    sql: ${TABLE}.cost_price ;;
    value_format_name: usd
  }

  measure: total_inventory_quantity {
    type: sum
    sql: ${TABLE}.inventory_quantity ;;
  }

  measure: total_locked_capital {
    type: sum
    sql: ${TABLE}.locked_capital ;;
    value_format_name: usd
  }

  measure: avg_attention_score {
    type: average
    sql: ${TABLE}.attention_score ;;
    value_format_name: decimal_2
  }

  measure: high_risk_product_count {
    type: count_distinct
    sql: CASE WHEN ${TABLE}.risk_tier = 'HIGH' THEN ${TABLE}.product_id END ;;
  }
}
