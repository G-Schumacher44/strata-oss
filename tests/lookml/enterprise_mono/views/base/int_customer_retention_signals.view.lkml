view: int_customer_retention_signals {
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

  dimension: first_name {
    type: string
    sql: ${TABLE}.first_name ;;
  }

  dimension: last_name {
    type: string
    sql: ${TABLE}.last_name ;;
  }

  dimension: customer_status {
    type: string
    sql: ${TABLE}.customer_status ;;
  }

  dimension: loyalty_tier {
    type: string
    sql: ${TABLE}.loyalty_tier ;;
  }

  dimension: clv_bucket {
    type: string
    sql: ${TABLE}.clv_bucket ;;
  }

  dimension: last_purchase_date {
    type: date
    sql: ${TABLE}.last_purchase_date ;;
  }

  dimension: marketing_opt_in {
    type: yesno
    sql: ${TABLE}.marketing_opt_in ;;
  }

  dimension: snapshot_dt {
    type: date
    sql: ${TABLE}.snapshot_dt ;;
  }

  measure: total_orders {
    type: sum
    sql: ${TABLE}.total_orders ;;
  }

  measure: customer_count {
    type: count_distinct
    sql: ${TABLE}.customer_id ;;
  }

  measure: opted_in_customers {
    type: count_distinct
    sql: CASE WHEN ${TABLE}.marketing_opt_in THEN ${TABLE}.customer_id END ;;
  }
}
