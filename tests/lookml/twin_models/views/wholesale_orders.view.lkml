view: wholesale_orders {
  sql_table_name: twin.wholesale_orders ;;
  dimension: id {
    primary_key: yes
    sql: ${TABLE}.id ;;
  }
  dimension: account_id {
    sql: ${TABLE}.account_id ;;
  }
}
