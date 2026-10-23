# Output: bq_query_guardrail

## Guardrail Result: APPROVED

**Estimated cost:** 2.14 GB (~$0.01 at $5/TB)

## Checks
- [x] Cost within threshold (2.14 GB / limit 100 GB)
- [x] No SELECT *
- [x] Partition filter present (`created_date BETWEEN '2026-01-01' AND '2026-03-31'`)
- [x] No CROSS JOIN
- [x] Date range bounded (Q1 2026 — 90 days)

## Issues
None.

## Recommendation
Query is approved. Proceed to execution.
