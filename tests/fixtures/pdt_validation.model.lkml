connection: "analytics_readonly"
include: "*.view.lkml"

explore: pdt_scope {
  from: pdt_scope_orders
}
