connection: "acme-analytics"

include: "/models/em_finance_base.model.lkml"
include: "/models/em_executive_base.model.lkml"
include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: finance_detailed {
  extends: [finance]
  label: "Finance (Detailed)"
  description: "Finance reporting with full channel and margin breakdown — extends base finance"
}

explore: executive_finance {
  extends: [executive_summary]
  label: "Executive Finance View"
  description: "C-suite finance overlay — extends executive_summary for finance team access"
}
