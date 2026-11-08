view: accounts {
  sql_table_name: twin.accounts ;;
  dimension: id {
    primary_key: yes
    sql: ${TABLE}.id ;;
  }
}
