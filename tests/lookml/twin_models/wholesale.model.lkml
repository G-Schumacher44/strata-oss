connection: "twin"

include: "/views/*.view.lkml"

explore: orders {
  from: wholesale_orders
}

# A refinement in this model refines this model's explore only.
explore: +orders {
  join: accounts {
    type: left_outer
    sql_on: ${orders.account_id} = ${accounts.id} ;;
    relationship: many_to_one
  }
}
