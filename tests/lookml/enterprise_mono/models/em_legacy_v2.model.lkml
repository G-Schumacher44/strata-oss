connection: "acme-analytics"

include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"
include: "/views/legacy/*.view.lkml"

# DEAD — these explores were the original acme-analytics explores before
# the model restructuring initiative. Superseded by em_orders_base and em_finance_base.
# The pdt_customer_value_score and pdt_attribution_full_funnel PDTs were built
# to serve these explores — killing the PDTs without removing these explores first
# would have left zombied schedules. Both explores have had zero queries since Q3 2025.

explore: dead_orders_v2 {
  label: "Orders v2 (Deprecated)"
  from: int_attributed_purchases
  join: pdt_customer_value_score {
    type: left_outer
    sql_on: ${int_attributed_purchases.order_id} = ${pdt_customer_value_score.customer_id} ;;
    relationship: many_to_one
  }
}

explore: dead_finance_v2 {
  label: "Finance v2 (Deprecated)"
  from: fct_finance_revenue
  join: pdt_attribution_full_funnel {
    type: left_outer
    sql_on: ${fct_finance_revenue.order_date} = ${pdt_attribution_full_funnel.metric_date} ;;
    relationship: one_to_many
  }
}
