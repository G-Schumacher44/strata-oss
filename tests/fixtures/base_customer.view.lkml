view: base_customer {
  sql_table_name: analytics.customers ;;

  dimension: id {
    type: number
    primary_key: yes
    sql: ${TABLE}.id ;;
    tags: ["pk", "customer"]
  }

  dimension: email {
    type: string
    sql: ${TABLE}.email ;;
  }

  dimension: state {
    type: string
    sql: ${TABLE}.state ;;
  }

  dimension: created_date {
    type: date
    sql: ${TABLE}.created_at ;;
  }

  dimension: status {
    type: string
    sql: ${TABLE}.status ;;
  }

  measure: count {
    type: count
    sql: ${id} ;;
  }

  measure: active_count {
    type: count
    filters: [status: "active"]
    sql: ${id} ;;
  }
}
