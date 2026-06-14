view: simple {
  sql_table_name: analytics.simple ;;

  dimension: id {
    type: number
    primary_key: yes
    sql: ${TABLE}.id ;;
    tags: ["core"]
  }

  measure: count {
    type: count
    sql: ${id} ;;
  }
}
