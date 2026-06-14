connection: "acme-analytics"

include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: orders {
  label: "Orders"
  from: int_attributed_purchases
  join: int_customer_retention_signals {
    type: left_outer
    sql_on: ${int_attributed_purchases.order_id} = ${int_customer_retention_signals.customer_id} ;;
    relationship: many_to_one
  }
  join: fct_daily_dashboard {
    type: left_outer
    sql_on: ${int_attributed_purchases.order_dt} = ${fct_daily_dashboard.metric_date} ;;
    relationship: many_to_one
  }
}

explore: order_detail {
  label: "Order Line Detail"
  from: int_attributed_purchases
  join: fct_product_profitability {
    type: left_outer
    sql_on: ${int_attributed_purchases.order_dt} = ${fct_product_profitability.product_date} ;;
    relationship: many_to_many
  }
  join: pdt_sales_velocity {
    type: left_outer
    sql_on: ${fct_product_profitability.product_id} = ${pdt_sales_velocity.product_id}
            AND ${fct_product_profitability.product_date} = ${pdt_sales_velocity.order_date} ;;
    relationship: one_to_one
  }
}
