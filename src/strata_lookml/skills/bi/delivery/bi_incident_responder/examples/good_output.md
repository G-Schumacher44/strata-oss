# Output: bi_incident_responder

## Incident Brief — Revenue by Region showing $0 since ~08:00 UTC

**Reported:** 2026-06-07 ~08:00 UTC
**Scope:** enterprise.finance_overview / total_revenue
**Symptom type:** Zero

---

## Evidence

| Check | Result |
|---|---|
| Explore in dead code register | NO — finance_overview is live (892 queries last 30 days) |
| Schema drift hits on backing views | 1 hit — `finance_orders.customer_region` renamed from `region` 3 days ago |
| PDT build status | FAILED — `pdt_finance_daily_summary` last successful build 2026-06-06 23:47 UTC |
| Join graph risk | `many_to_one` join on `finance_customers` — relationship declared, OK |

---

## Hypotheses (ranked)

1. **PDT build failure** — `pdt_finance_daily_summary` failed overnight. The `total_revenue` measure
   sources from this PDT. A failed PDT build leaves the table empty or stale, causing $0.
   Evidence: PDT status = FAILED, symptom appeared at ~08:00 (matches overnight PDT rebuild window).

2. **Schema drift on `finance_orders.customer_region`** — The column rename from `region` to
   `customer_region` 3 days ago may have broken the PDT SQL if it references `${TABLE}.region`.
   Evidence: 1 drift hit on the backing view; this could be the root cause of the PDT failure.

---

## Next Diagnostic Steps

1. To confirm hypothesis 1: Check PDT build logs — `bq show --format=prettyjson acme-data.looker_scratch.pdt_finance_daily_summary` and look for build errors. If empty table, PDT failed.
2. To confirm hypothesis 2: Read `finance_orders.view.lkml` and search for `${TABLE}.region` — if present, the column rename is breaking the PDT SQL, which is the root cause of both the drift hit and the PDT failure.

---

## Suggested Next Skill
`lookml_view_reviewer` on `finance_orders` — to confirm the drift hit and identify the broken SQL field reference before attempting a PDT rebuild.
