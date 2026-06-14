connection: "acme-analytics"

include: "/models/em_shipping_base.model.lkml"
include: "/views/base/*.view.lkml"

explore: shipping_apac {
  extends: [shipping]
  label: "Shipping (APAC)"
  description: "Shipping and logistics scoped to APAC region — extends base shipping explore"
}
