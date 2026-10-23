# Output: release_notes_generator

## BI Release Notes — 2026-06-07
Add net_revenue measure, retire legacy_customers explore

### New This Release
- **Orders / Net Revenue** — revenue after refunds and discounts. Available in all reports that use the Orders data source. Use this metric for financial reporting; Gross Revenue remains available for sales performance reporting.

### Retired ⚠️
- **Legacy Customers** — this data source has been retired and is no longer available in Looker. Contact the BI team if you need historical customer data from this source.

### Breaking Changes ⚠️
- **Gross Revenue (Legacy)** removed from the **Legacy Customers** data source. Any saved reports or dashboards using this field will display an error. Please update to use the **Orders** data source instead, or contact the BI team for migration support.

---

*Released by the BI team · Questions? Reach us in #bi-support*
