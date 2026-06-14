# LEGACY — warehouse_zone and reorder_threshold dropped when 3PL integration
# replaced the on-prem WMS in Q3 2024. This view was never updated.
# Schema drift: warehouse_zone, reorder_threshold absent from int_inventory_risk.
view: legacy_inventory_snapshot {
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

  # DRIFT: warehouse_zone removed after 3PL migration
  dimension: warehouse_zone {
    type: string
    sql: ${TABLE}.warehouse_zone ;;
  }

  dimension: risk_tier {
    type: string
    sql: ${TABLE}.risk_tier ;;
  }

  # DRIFT: reorder_threshold dropped — replaced by attention_score
  dimension: reorder_threshold {
    type: number
    sql: ${TABLE}.reorder_threshold ;;
  }

  measure: total_inventory {
    type: sum
    sql: ${TABLE}.inventory_quantity ;;
  }

  measure: total_locked_capital {
    type: sum
    sql: ${TABLE}.locked_capital ;;
    value_format_name: usd
  }

  measure: product_count {
    type: count_distinct
    sql: ${TABLE}.product_id ;;
  }
}
