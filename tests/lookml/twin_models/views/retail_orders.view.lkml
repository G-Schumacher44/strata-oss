view: retail_orders {
  sql_table_name: twin.retail_orders ;;
  dimension: id {
    primary_key: yes
    sql: ${TABLE}.id ;;
  }
}
