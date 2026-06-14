connection: "analytics_readonly"
include: "*.view.lkml"

explore: customer {
  from: customer_extended

  join: chain_final {
    type: left_outer
    relationship: one_to_many
    sql_on: ${customer_extended.id} = ${chain_final.id} ;;
  }
}

explore: orphan_explore {
  from: simple
}
