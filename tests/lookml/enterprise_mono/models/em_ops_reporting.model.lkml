connection: "acme-analytics"

include: "/models/em_products_base.model.lkml"
include: "/models/em_ops_base.model.lkml"
include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: products_ops {
  extends: [products]
  label: "Products (Ops)"
  description: "Product profitability for ops team — extends base products with ops context"
}

explore: ops_detailed {
  extends: [daily_ops]
  label: "Daily Ops (Detailed)"
  description: "Full daily ops with shipping and cost breakdown — extends daily_ops"
}
