view: chain_base {
  sql_table_name: analytics.chain_base ;;

  dimension: id {
    type: number
    sql: ${TABLE}.id ;;
  }

  dimension: base_only {
    type: string
    sql: ${TABLE}.base_only ;;
  }
}

view: chain_middle {
  extends: [chain_base]

  dimension: middle_only {
    type: string
    sql: ${TABLE}.middle_only ;;
  }

  dimension: base_only {
    type: string
    sql: UPPER(${TABLE}.base_only) ;;
  }
}

view: chain_final {
  extends: [chain_middle]

  dimension: final_only {
    type: string
    sql: ${TABLE}.final_only ;;
  }

  measure: final_count {
    type: count
    sql: ${id} ;;
  }
}
