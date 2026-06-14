view: pdt_regional_kpi {
  derived_table: {
    sql:
      SELECT
        f.order_date,
        f.order_channel,
        f.gross_revenue,
        f.net_revenue,
        f.shipping_margin,
        d.orders_count,
        d.return_rate,
        d.cart_conversion_rate,
        d.revenue_anomaly_flag
      FROM `acme-analytics.gold_marts.fct_finance_revenue` f
      LEFT JOIN `acme-analytics.gold_marts.fct_daily_dashboard` d
        ON f.order_date = d.metric_date
      WHERE f.order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
    ;;
    persist_for: "12 hours"
  }

  dimension: order_date {
    type: date
    sql: ${TABLE}.order_date ;;
    primary_key: yes
  }

  dimension: order_channel {
    type: string
    sql: ${TABLE}.order_channel ;;
  }

  dimension: revenue_anomaly_flag {
    type: yesno
    sql: ${TABLE}.revenue_anomaly_flag ;;
  }

  measure: gross_revenue {
    type: sum
    sql: ${TABLE}.gross_revenue ;;
    value_format_name: usd
  }

  measure: net_revenue {
    type: sum
    sql: ${TABLE}.net_revenue ;;
    value_format_name: usd
  }

  measure: shipping_margin {
    type: sum
    sql: ${TABLE}.shipping_margin ;;
    value_format_name: usd
  }

  measure: total_orders {
    type: sum
    sql: ${TABLE}.orders_count ;;
  }

  measure: avg_return_rate {
    type: average
    sql: ${TABLE}.return_rate ;;
    value_format_name: percent_2
  }
}
