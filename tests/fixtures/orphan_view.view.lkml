view: orphan_view {
  sql_table_name: analytics.orphan_view ;;

  dimension: id {
    type: number
    sql: ${TABLE}.id ;;
  }

  measure: count {
    type: count
    sql: ${id} ;;
  }
}
