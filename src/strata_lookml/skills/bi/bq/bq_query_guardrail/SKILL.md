# Skill: bq_query_guardrail

domain: bi/bq
mode: validate
complexity: low
version: 0.1.0

> Dry-run any SQL before execution. Gives task-scoped agents a hard stop instead of
> "think harder." Blocks expensive, dangerous, or malformed queries before they
> reach BQ.

---

## Trigger

- Before executing ANY BQ query that is not a `SELECT * LIMIT 5` sample
- Automatically after SQL draft is produced by any skill
- Before passing SQL to Looker MCP for explore validation

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `sql` | yes | prior skill / human | SQL string to validate |
| `cost_threshold_gb` | no | `~/.strata/config.json` → `cost_threshold_gb` (default: 100 GB) | GB ceiling for dry-run; queries above this are hard-stopped |
| `bq_project` | no | gcloud default project; override via `~/.strata/config.json` → `bq_project` or `STRATA_BQ_PROJECT` | Only needed if tables use 2-part names (`dataset.table`); 3-part names are self-contained |

---

## Allowed Tools

- `bq_cli`: `bq query --dry_run --nouse_legacy_sql`

---

## Forbidden

- Do not execute the query (no `bq query` without `--dry_run`)
- Do not modify the SQL to pass checks — report failures, do not silently fix
- Do not approve queries that trigger any hard-stop check

---

## Procedure

1. Run: `bq query --dry_run --nouse_legacy_sql --project_id=PROJECT "SQL"`
2. Parse bytes processed from the response line ("will process X bytes of data")
3. Convert bytes → GB. If > `cost_threshold_gb` → **HARD STOP** (cost)
4. Check for `SELECT *` with no column list → flag (not hard stop, warn)
5. Check for missing `WHERE` clause on date/partition column → **HARD STOP** (partition scan)
6. Check for `CROSS JOIN` → **HARD STOP** (fanout risk)
7. Check for unbounded date range (no date filter at all) → **HARD STOP**
8. Check for multiple `JOIN`s on the same table without aliasing → flag (fanout risk)
9. `[JUDGMENT]` If dry-run returns an error: determine if it's a syntax error (fixable) or access error (escalate). State which.
10. If all checks pass → output APPROVED with cost estimate

---

## Stop Conditions

- Any HARD STOP check triggered → halt immediately, do not proceed to execution
- Dry-run API error → halt, report exact error
- Cost > threshold → halt even if all other checks pass

---

## Output Format

```markdown
## Guardrail Result: APPROVED / BLOCKED

**Estimated cost:** X.XX GB (~$Y.YY at $5/TB)

## Checks
- [ ] Cost within threshold (X GB / limit Y GB)
- [ ] No SELECT *
- [ ] Partition filter present
- [ ] No CROSS JOIN
- [ ] Date range bounded

## Issues
[If BLOCKED: list each triggered check with the specific SQL line causing it]

## Recommendation
[If BLOCKED: one sentence on what to fix. Do not rewrite the SQL.]
```

---

## Escalation

> "BLOCKED. Query scans [X] GB which exceeds the [Y] GB threshold. Reduce scope
> by adding a partition filter on `[date_col]` or narrowing the date range."

> "BLOCKED. Query contains CROSS JOIN which risks row multiplication. Confirm
> the join logic is intentional before proceeding."

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
