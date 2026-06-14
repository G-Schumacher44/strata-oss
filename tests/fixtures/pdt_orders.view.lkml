view: pdt_orders {
  derived_table: {
    sql:
      SELECT customer_id, COUNT(*) AS order_count
      FROM analytics.orders
      GROUP BY customer_id ;;
    persist_for: "24 hours"
  }

  dimension: customer_id {
    type: number
    sql: ${TABLE}.customer_id ;;
  }

  measure: order_count {
    type: sum
    sql: ${TABLE}.order_count ;;
  }
}
