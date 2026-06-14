connection: "acme-analytics"

include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: executive_summary {
  label: "Executive Dashboard"
  from: fct_daily_dashboard
  join: fct_finance_revenue {
    type: left_outer
    sql_on: ${fct_daily_dashboard.metric_date} = ${fct_finance_revenue.order_date} ;;
    relationship: one_to_many
  }
  join: fct_sales_operations {
    type: left_outer
    sql_on: ${fct_daily_dashboard.metric_date} = ${fct_sales_operations.order_date} ;;
    relationship: one_to_many
  }
  join: fct_customer_segments {
    type: left_outer
    sql_on: 1=1 ;;
    relationship: many_to_many
  }
  join: pdt_regional_kpi {
    type: left_outer
    sql_on: ${fct_daily_dashboard.metric_date} = ${pdt_regional_kpi.order_date} ;;
    relationship: one_to_many
  }
}
