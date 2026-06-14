connection: "acme-analytics"

include: "/models/em_orders_base.model.lkml"
include: "/models/em_marketing_base.model.lkml"
include: "/views/base/*.view.lkml"

explore: orders_eu {
  extends: [orders]
  label: "Orders (EU)"
  description: "Order analysis scoped to EU region — extends base orders explore"
}

explore: marketing_eu {
  extends: [marketing]
  label: "Marketing (EU)"
  description: "Marketing attribution scoped to EU channels — extends base marketing explore"
}
