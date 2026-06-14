# NT (Native Table / explore_source PDT) — rebuilds every 4 hours, processes ~40TB per run.
# Cost: ~$1,500/day, ~$45K/month. The explore it backed (dead_finance_v2) went dark Q4 2025.
# The Looker NT scheduler kept triggering builds. Strata flagged $540K/year in zombie compute.
view: pdt_attribution_full_funnel {
  derived_table: {
    explore_source: marketing {
      column: metric_date {}
      column: channel {}
      column: recovered_orders {}
      column: total_orders {}
      column: abandoned_carts {}
      column: converted_carts {}
      column: abandoned_value {}
      column: avg_time_to_purchase_hours {}
      column: cart_recovery_rate {}
    }
    persist_for: "4 hours"
  }

  dimension: metric_date {
    type: date
    sql: ${TABLE}.metric_date ;;
    primary_key: yes
  }

  dimension: channel {
    type: string
    sql: ${TABLE}.channel ;;
  }

  measure: total_recovered_orders {
    type: sum
    sql: ${TABLE}.recovered_orders ;;
  }

  measure: total_abandoned_value {
    type: sum
    sql: ${TABLE}.abandoned_value ;;
    value_format_name: usd
  }

  measure: avg_recovery_rate {
    type: average
    sql: ${TABLE}.cart_recovery_rate ;;
    value_format_name: percent_2
  }
}
