connection: "acme-analytics"

include: "/models/em_marketing_base.model.lkml"
include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: marketing_detailed {
  extends: [marketing]
  label: "Marketing (Detailed)"
  description: "Full marketing funnel with customer segment overlay — extends base marketing"
}

explore: cart_deep_dive {
  extends: [cart_analysis]
  label: "Cart Abandonment Deep Dive"
  description: "Granular cart recovery analysis — extends base cart_analysis"
}
