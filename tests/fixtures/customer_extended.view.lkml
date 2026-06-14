view: customer_extended {
  extends: [base_customer]
  sql_table_name: analytics.customer_snapshot ;;

  dimension: email {
    type: string
    sql: LOWER(${TABLE}.email) ;;
    tags: ["normalized"]
  }

  dimension: lifetime_value {
    type: number
    sql: ${TABLE}.lifetime_value ;;
  }

  dimension: segment {
    type: string
    sql: ${TABLE}.segment ;;
  }
}
