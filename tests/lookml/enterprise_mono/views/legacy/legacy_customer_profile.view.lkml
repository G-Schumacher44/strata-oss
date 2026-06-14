# LEGACY — predates customer_status unification in Q2 2025.
# customer_status_v1 was a free-text field split into customer_status + loyalty_tier.
# Schema drift: customer_status_v1 absent from int_customer_retention_signals since v2.
view: legacy_customer_profile {
  sql_table_name: `acme-analytics.silver.int_customer_retention_signals` ;;

  dimension: customer_id {
    type: string
    sql: ${TABLE}.customer_id ;;
    primary_key: yes
  }

  dimension: email {
    type: string
    sql: ${TABLE}.email ;;
  }

  # DRIFT: customer_status_v1 replaced by customer_status + loyalty_tier in v2
  dimension: legacy_status {
    type: string
    sql: ${TABLE}.customer_status_v1 ;;
  }

  dimension: loyalty_tier {
    type: string
    sql: ${TABLE}.loyalty_tier ;;
  }

  dimension: last_purchase_date {
    type: date
    sql: ${TABLE}.last_purchase_date ;;
  }

  # DRIFT: segment_score_v1 computed from customer_status_v1, also dropped
  dimension: segment_score {
    type: number
    sql: ${TABLE}.segment_score_v1 ;;
  }

  measure: customer_count {
    type: count_distinct
    sql: ${TABLE}.customer_id ;;
  }

  measure: total_orders {
    type: sum
    sql: ${TABLE}.total_orders ;;
  }
}
