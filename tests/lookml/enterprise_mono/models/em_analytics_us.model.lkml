connection: "acme-analytics"

include: "/models/em_customers_base.model.lkml"
include: "/models/em_orders_base.model.lkml"
include: "/models/em_finance_base.model.lkml"
include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: customers_us {
  extends: [customers]
  label: "Customers (US)"
  description: "Customer analysis scoped to US region — extends base customers explore"
}

explore: orders_us {
  extends: [orders]
  label: "Orders (US)"
  description: "Order analysis scoped to US region — extends base orders explore"
}

explore: finance_us {
  extends: [finance]
  label: "Finance (US)"
  description: "Finance & revenue scoped to US channels — extends base finance explore"
}
