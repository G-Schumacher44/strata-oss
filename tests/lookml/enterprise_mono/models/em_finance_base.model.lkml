connection: "acme-analytics"

include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: finance {
  label: "Finance & Revenue"
  from: fct_finance_revenue
  join: fct_daily_dashboard {
    type: left_outer
    sql_on: ${fct_finance_revenue.order_date} = ${fct_daily_dashboard.metric_date} ;;
    relationship: many_to_one
  }
  join: pdt_regional_kpi {
    type: left_outer
    sql_on: ${fct_finance_revenue.order_date} = ${pdt_regional_kpi.order_date}
            AND ${fct_finance_revenue.order_channel} = ${pdt_regional_kpi.order_channel} ;;
    relationship: one_to_one
  }
}

explore: revenue_trends {
  label: "Revenue Trend Analysis"
  from: fct_daily_dashboard
  join: fct_finance_revenue {
    type: left_outer
    sql_on: ${fct_daily_dashboard.metric_date} = ${fct_finance_revenue.order_date} ;;
    relationship: one_to_many
  }
}
