connection: "legacy_redshift"

include: "/views/legacy/*.view.lkml"

# DEAD — legacy_redshift cluster was decommissioned Q2 2025. These explores
# cannot execute. Retained for historical dashboard link compatibility only.
# Zero queries since decommission. Candidate for deletion after dashboard audit.

explore: legacy_orders {
  label: "Orders (Legacy Redshift)"
  from: legacy_order_detail
}

explore: legacy_customers {
  label: "Customers (Legacy Redshift)"
  from: legacy_customer_profile
}

explore: legacy_inventory {
  label: "Inventory (Legacy Redshift)"
  from: legacy_inventory_snapshot
}
