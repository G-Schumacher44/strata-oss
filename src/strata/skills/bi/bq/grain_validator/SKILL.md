# Skill: grain_validator

domain: bi/bq
mode: validate
complexity: medium
version: 0.1.0

> Confirm the grain of a BQ table before writing SQL against it.
> Wrong grain assumptions are the #1 source of inflated metrics. Run this
> before any JOIN or aggregation on an unfamiliar table.

---

## Trigger

- About to JOIN two tables for the first time
- A metric looks inflated or doubled after a query
- Unfamiliar table — grain not documented
- After `bq_schema_probe` surfaces a candidate PK but you're not certain

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `table` | yes | human / bq_schema_probe | Fully-qualified BQ table name |
| `candidate_pk` | no | bq_schema_probe | Column(s) suspected to define uniqueness |
| `bq_project` | no | gcloud default project; override via `~/.strata/config.json` → `bq_project` or `STRATA_BQ_PROJECT` | Only needed if `table` uses a 2-part name (`dataset.table`) |

---

## Allowed Tools

- `bq_cli`: `bq query --dry_run` and `bq query --nouse_legacy_sql`

---

## Forbidden

- Do not run queries without `--dry_run` first (invoke `bq_query_guardrail` implicitly)
- Do not assume grain from column names alone — always verify with a count check
- Do not modify any table

---

## Procedure

1. If `candidate_pk` provided: skip to step 3. Otherwise inspect schema from `bq show --schema {table}`
2. `[JUDGMENT]` Identify candidate PK columns: look for columns named `id`, `key`, `uuid`, or that match the table name + `_id`. Note date/timestamp columns separately.
3. Dry-run uniqueness check:
   ```sql
   SELECT {candidate_pk}, COUNT(*) AS n
   FROM `{table}`
   GROUP BY {candidate_pk}
   HAVING n > 1
   LIMIT 1
   ```
4. Load skill `bq_query_guardrail` via `strata_skill("bq_query_guardrail")` and follow its procedure → if BLOCKED, halt and surface reason
5. Execute uniqueness query (add `WHERE date_col >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)` if partitioned)
6. If result is empty → grain confirmed at `candidate_pk` level
7. If rows returned → duplicates exist. Check if a secondary column resolves them (e.g. `status`, `version`, `event_type`)
8. `[JUDGMENT]` Determine if duplicates are expected (SCD, event log) or a data quality issue
9. Count total rows vs distinct PK rows:
   ```sql
   SELECT COUNT(*) AS total, COUNT(DISTINCT {candidate_pk}) AS unique_keys FROM `{table}` LIMIT 1
   ```
10. Output grain verdict

---

## Stop Conditions

- Dry-run cost > threshold → halt, report, do not execute
- No plausible PK candidate found after reviewing all columns → halt, escalate
- Table does not exist → halt immediately

---

## Output Format

```markdown
## Grain Validation — `{table}`

**Candidate PK:** `{columns}`
**Verdict:** CONFIRMED / UNRESOLVED / DUPLICATE EXPECTED

**Row count:** {total}
**Unique key count:** {unique}
**Duplicate rate:** {pct}%

## Grain Statement
One row = one {plain-english description of what a row represents}.

## Duplicate Detail (if any)
- Cause: [SCD type 2 / event log / data quality issue / unknown]
- Resolution: [dedup with ROW_NUMBER() / filter on status='active' / investigate]

## JOIN Safety
- Safe to JOIN on {columns} without aggregation: YES / NO
- If NO: [one sentence on required dedup step before joining]
```

---

## Escalation

> "Halt. Table `{table}` has a {pct}% duplicate rate on `{candidate_pk}`. This
> table cannot be joined without deduplication. Confirm the expected grain with
> the data owner before proceeding."

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
