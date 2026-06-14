connection: "acme-analytics"

include: "/models/em_customers_base.model.lkml"
include: "/models/em_orders_base.model.lkml"
include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: customers_ds {
  extends: [customers]
  label: "Customers (DS Access)"
  description: "Customer data for data science team — extends base customers, includes cohort PDT"
  join: pdt_cohort_retention {
    type: left_outer
    sql_on: ${int_customer_lifetime_value.customer_segment} = ${pdt_cohort_retention.cohort_month} ;;
    relationship: one_to_many
  }
}

explore: orders_ds {
  extends: [orders]
  label: "Orders (DS Access)"
  description: "Order data for data science team — extends base orders explore"
}
