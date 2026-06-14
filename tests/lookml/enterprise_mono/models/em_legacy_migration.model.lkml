connection: "legacy_warehouse_v1"

include: "/views/legacy/*.view.lkml"

# BROKEN — legacy_warehouse_v1 connection was never migrated to the new connector
# naming convention (should be "acme-analytics"). Looker refuses to execute
# queries. Created during the data warehouse migration sprint; the explore was
# never tested against the new connection after rename.

explore: migration_orders {
  label: "Orders (Migration Test — BROKEN)"
  from: legacy_order_detail
  join: legacy_customer_profile {
    type: left_outer
    sql_on: ${legacy_order_detail.order_id} = ${legacy_customer_profile.customer_id} ;;
    relationship: many_to_one
  }
}
