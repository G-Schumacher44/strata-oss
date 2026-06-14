connection: "acme-analytics"

include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: products {
  label: "Product Profitability"
  from: fct_product_profitability
  join: int_inventory_risk {
    type: left_outer
    sql_on: ${fct_product_profitability.product_id} = ${int_inventory_risk.product_id} ;;
    relationship: one_to_one
  }
  join: pdt_sales_velocity {
    type: left_outer
    sql_on: ${fct_product_profitability.product_id} = ${pdt_sales_velocity.product_id}
            AND ${fct_product_profitability.product_date} = ${pdt_sales_velocity.order_date} ;;
    relationship: one_to_one
  }
}

explore: sales_ops {
  label: "Sales Operations"
  from: fct_sales_operations
  join: fct_product_profitability {
    type: left_outer
    sql_on: ${fct_sales_operations.product_id} = ${fct_product_profitability.product_id}
            AND ${fct_sales_operations.order_date} = ${fct_product_profitability.product_date} ;;
    relationship: one_to_one
  }
  join: int_inventory_risk {
    type: left_outer
    sql_on: ${fct_sales_operations.product_id} = ${int_inventory_risk.product_id} ;;
    relationship: one_to_one
  }
}
