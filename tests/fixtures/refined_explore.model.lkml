connection: "analytics_readonly"
include: "*.view.lkml"

explore: refined_customer {
  from: customer_extended

  join: simple {
    type: left_outer
    relationship: many_to_one
    sql_on: ${customer_extended.id} = ${simple.id} ;;
  }
}

explore: +refined_customer {
  label: "Refined Customer"

  join: chain_final {
    type: left_outer
    relationship: one_to_one
    sql_on: ${customer_extended.id} = ${chain_final.id} ;;
  }
}
