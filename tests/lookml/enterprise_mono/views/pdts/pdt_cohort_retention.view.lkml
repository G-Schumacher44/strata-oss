view: pdt_cohort_retention {
  derived_table: {
    sql:
      SELECT
        DATE_TRUNC(r.first_order_date, MONTH) AS cohort_month,
        DATE_TRUNC(a.order_dt, MONTH) AS activity_month,
        COUNT(DISTINCT a.order_id) AS order_count,
        COUNT(DISTINCT r.customer_id) AS retained_customers,
        SUM(a.net_total) AS cohort_revenue
      FROM `acme-analytics.silver.int_customer_lifetime_value` r
      JOIN `acme-analytics.silver.int_attributed_purchases` a
        ON r.customer_id = a.order_id
      WHERE r.first_order_date IS NOT NULL
      GROUP BY 1, 2
    ;;
    persist_for: "24 hours"
  }

  dimension: cohort_month {
    type: date_month
    sql: ${TABLE}.cohort_month ;;
    primary_key: yes
  }

  dimension: activity_month {
    type: date_month
    sql: ${TABLE}.activity_month ;;
  }

  measure: retained_customers {
    type: sum
    sql: ${TABLE}.retained_customers ;;
  }

  measure: cohort_revenue {
    type: sum
    sql: ${TABLE}.cohort_revenue ;;
    value_format_name: usd
  }

  measure: avg_orders_per_customer {
    type: number
    sql: SAFE_DIVIDE(${order_count}, NULLIF(${retained_customers}, 0)) ;;
    value_format_name: decimal_2
  }

  measure: order_count {
    type: sum
    sql: ${TABLE}.order_count ;;
  }
}
