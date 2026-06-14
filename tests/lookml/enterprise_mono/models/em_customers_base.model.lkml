connection: "acme-analytics"

include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: customers {
  label: "Customers"
  from: fct_customer_segments
  join: int_customer_lifetime_value {
    type: left_outer
    sql_on: ${fct_customer_segments.customer_segment} = ${int_customer_lifetime_value.customer_segment} ;;
    relationship: one_to_many
  }
  join: int_customer_retention_signals {
    type: left_outer
    sql_on: ${int_customer_lifetime_value.customer_id} = ${int_customer_retention_signals.customer_id} ;;
    relationship: one_to_one
  }
}

explore: customer_segments {
  label: "Customer Segment Deep Dive"
  from: fct_customer_segments
  join: int_customer_lifetime_value {
    type: left_outer
    sql_on: ${fct_customer_segments.customer_segment} = ${int_customer_lifetime_value.customer_segment} ;;
    relationship: one_to_many
  }
}
