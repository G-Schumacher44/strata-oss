# G4 PDT — rebuilds every 6 hours, processes ~25TB per run (~$625/day).
# The explore that consumed this (dead_orders_v2) has had zero queries since Q3 2025.
# This PDT ran undetected for 8 months before Strata flagged it.
# Killing it saves ~$225K/year.
view: pdt_customer_value_score {
  derived_table: {
    sql:
      WITH clv_base AS (
        SELECT
          c.customer_id,
          c.customer_segment,
          c.predicted_clv_bucket,
          c.actual_clv_bucket,
          c.net_clv,
          c.order_count,
          c.return_count,
          c.days_since_last_order,
          c.avg_order_value,
          r.customer_status,
          r.loyalty_tier,
          r.marketing_opt_in
        FROM `acme-analytics.silver.int_customer_lifetime_value` c
        LEFT JOIN `acme-analytics.silver.int_customer_retention_signals` r
          ON c.customer_id = r.customer_id
      ),
      scored AS (
        SELECT
          *,
          CASE
            WHEN net_clv > 5000 AND days_since_last_order < 30 THEN 'PLATINUM'
            WHEN net_clv > 2500 AND days_since_last_order < 60 THEN 'GOLD'
            WHEN net_clv > 1000 AND days_since_last_order < 90 THEN 'SILVER'
            ELSE 'BRONZE'
          END AS value_tier,
          NTILE(100) OVER (ORDER BY net_clv DESC) AS clv_percentile,
          NTILE(100) OVER (ORDER BY days_since_last_order ASC) AS recency_percentile,
          ROW_NUMBER() OVER (PARTITION BY customer_segment ORDER BY net_clv DESC) AS segment_rank
        FROM clv_base
      ),
      enriched AS (
        SELECT
          s.*,
          p.units_sold,
          p.gross_revenue AS product_gross_revenue,
          p.net_margin AS product_net_margin,
          f.gross_revenue AS finance_gross_revenue,
          f.shipping_margin
        FROM scored s
        LEFT JOIN `acme-analytics.gold_marts.fct_product_profitability` p
          ON s.customer_id = p.product_id
        LEFT JOIN `acme-analytics.gold_marts.fct_finance_revenue` f
          ON DATE(CURRENT_TIMESTAMP()) = f.order_date
      )
      SELECT * FROM enriched
    ;;
    persist_for: "6 hours"
  }

  dimension: customer_id {
    type: string
    sql: ${TABLE}.customer_id ;;
    primary_key: yes
  }

  dimension: customer_segment {
    type: string
    sql: ${TABLE}.customer_segment ;;
  }

  dimension: value_tier {
    type: string
    sql: ${TABLE}.value_tier ;;
  }

  dimension: clv_percentile {
    type: number
    sql: ${TABLE}.clv_percentile ;;
  }

  dimension: recency_percentile {
    type: number
    sql: ${TABLE}.recency_percentile ;;
  }

  dimension: loyalty_tier {
    type: string
    sql: ${TABLE}.loyalty_tier ;;
  }

  measure: total_customers {
    type: count_distinct
    sql: ${TABLE}.customer_id ;;
  }

  measure: avg_clv {
    type: average
    sql: ${TABLE}.net_clv ;;
    value_format_name: usd
  }

  measure: platinum_customers {
    type: count_distinct
    sql: CASE WHEN ${TABLE}.value_tier = 'PLATINUM' THEN ${TABLE}.customer_id END ;;
  }
}
