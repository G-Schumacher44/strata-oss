connection: "acme-analytics"

include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: daily_ops {
  label: "Daily Operations"
  from: fct_daily_dashboard
  join: fct_finance_revenue {
    type: left_outer
    sql_on: ${fct_daily_dashboard.metric_date} = ${fct_finance_revenue.order_date} ;;
    relationship: one_to_many
  }
  join: fct_shipping_analysis {
    type: left_outer
    sql_on: ${fct_daily_dashboard.metric_date} = ${fct_shipping_analysis.order_date} ;;
    relationship: one_to_many
  }
}
