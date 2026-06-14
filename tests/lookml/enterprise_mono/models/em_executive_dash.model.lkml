connection: "acme-analytics"

include: "/models/em_executive_base.model.lkml"
include: "/views/base/*.view.lkml"
include: "/views/pdts/*.view.lkml"

explore: executive_kpi {
  extends: [executive_summary]
  label: "Executive KPI Board"
  description: "Board-level KPI view — extends executive_summary with anomaly focus"
}
