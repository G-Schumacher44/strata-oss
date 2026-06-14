connection: "acme-analytics"

include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: shipping {
  label: "Shipping & Logistics"
  from: fct_shipping_analysis
  join: fct_finance_revenue {
    type: left_outer
    sql_on: ${fct_shipping_analysis.order_date} = ${fct_finance_revenue.order_date}
            AND ${fct_shipping_analysis.order_channel} = ${fct_finance_revenue.order_channel} ;;
    relationship: many_to_one
  }
}
