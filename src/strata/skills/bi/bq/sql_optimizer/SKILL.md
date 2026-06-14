# Skill: sql_optimizer

domain: bi/bq
mode: audit
complexity: high
version: 0.1.0

> Analyze and rewrite slow or expensive BigQuery SQL. Targets the structural
> patterns that cause runaway costs: missing partition filters, unbounded scans,
> fanout joins, repeated subqueries, and over-aggregation. Returns a rewritten
> query with an explanation of every change and a before/after cost estimate.

---

## Trigger

- Query is slow (> 30s wall time) or expensive (> 50 GB scanned)
- BQ slot contention traced to a specific query
- Looker PDT build time exceeds acceptable threshold
- `sql_builder` draft passes guardrail but cost estimate is uncomfortably high
- "Can you make this query faster / cheaper?"

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `sql` | yes | human / sql_builder | SQL to optimize |
| `execution_stats` | no | BQ job history | Actual bytes processed, slot ms, wall time |
| `schema` | no | bq_schema_probe | Schema structs for tables in the query |
| `grain` | no | grain_validator | Confirmed grain (needed to assess JOIN safety) |
| `bq_project` | no | gcloud default project; override via `~/.strata/config.json` → `bq_project` or `STRATA_BQ_PROJECT` | Only needed if SQL uses 2-part table names (`dataset.table`); 3-part names are self-contained |

---

## Allowed Tools

- `bq_schema_probe` — if schema not provided and table structure is needed to assess optimization
- `bq_query_guardrail` — validate every rewrite before returning it
- `bq_cli`: `bq query --dry_run --nouse_legacy_sql` (via guardrail only)

---

## Forbidden

- Do not execute any query
- Do not change the semantic output — only change how it's computed
- Do not remove filters that affect correctness — only remove redundant ones
- Do not introduce approximation functions (`APPROX_COUNT_DISTINCT`, etc.) unless explicitly requested
- Do not optimize by removing partition filters to widen a date range

---

## Procedure

### Phase 1 — Diagnose

1. If `execution_stats` provided: identify the dominant cost driver (bytes scanned, slot ms, shuffle bytes). Otherwise dry-run original SQL via `bq_query_guardrail` for a bytes estimate.
2. Parse the SQL and classify every issue found:

| Pattern | Severity | Fix |
|---|---|---|
| Missing partition filter on a date/timestamp column | CRITICAL | Add `WHERE date_col BETWEEN ...` |
| `SELECT *` in an intermediate or final CTE | HIGH | Enumerate required columns only |
| Subquery repeated more than once | HIGH | Promote to a single CTE |
| `CROSS JOIN` | HIGH | Replace with conditional `JOIN` or confirm intentional |
| `NOT IN (SELECT ...)` on a large table | HIGH | Replace with `LEFT JOIN ... IS NULL` |
| `DISTINCT` on a large result without partition filter | HIGH | Add filter first, then DISTINCT |
| Multiple aggregation levels in one query without CTEs | MEDIUM | Decompose into CTEs |
| `ORDER BY` on a large result without `LIMIT` | MEDIUM | Add `LIMIT` or remove `ORDER BY` |
| `COUNT(DISTINCT x)` in a window function | MEDIUM | Use `APPROX_COUNT_DISTINCT` if exactness not required (flag for human decision) |
| Nested `SELECT` where a window function suffices | MEDIUM | Rewrite with `QUALIFY ROW_NUMBER() OVER (...)` |
| Unnecessary `GROUP BY` on a primary key column | LOW | Remove redundant grouping keys |
| String concatenation in a `JOIN` condition | LOW | Cast or pre-compute before joining |

3. `[JUDGMENT]` Prioritize fixes: address CRITICAL first, then HIGH, then MEDIUM. Skip LOW if the query is already cheap.
4. If schema is required to confirm partition column names or JOIN keys — invoke `bq_schema_probe`.

### Phase 2 — Rewrite

5. Produce rewritten SQL applying the identified fixes:
   - CTE-first: one CTE per logical step
   - Each optimization clearly commented: `-- OPT: added partition filter`
   - Preserve all column names and aliases in the final SELECT
   - Do not change the output columns, types, or sort order unless the original was incorrect
6. Run rewrite through `bq_query_guardrail`. If BLOCKED → diagnose, fix, re-run once. If still BLOCKED → halt.
7. Compute savings: `(original_bytes - rewritten_bytes) / original_bytes * 100`

### Phase 3 — Output

8. Return structured report: original vs rewritten SQL, changes list, before/after cost.

---

## Stop Conditions

- Rewrite changes the semantic output (different rows or columns) → halt, flag the issue, do not return rewrite
- `bq_query_guardrail` blocks the rewrite after one revision → halt and explain
- SQL is already optimal (< 5 GB, no flagged patterns) → return original with a brief "no significant optimizations found" note

---

## Output Format

```markdown
## SQL Optimization Report

**Original cost estimate:** X.XX GB (~$Y.YY)
**Rewritten cost estimate:** X.XX GB (~$Y.YY)
**Savings:** {pct}% reduction

## Issues Found

| # | Pattern | Severity | Line(s) |
|---|---|---|---|
| 1 | Missing partition filter on `date_col` | CRITICAL | 12 |
| 2 | Repeated subquery `user_events` | HIGH | 8, 24 |

## Changes Made

1. **Added partition filter** on `date_col` — reduces full table scan to a single partition
2. **Promoted `user_events` to a CTE** — eliminates duplicate scan
3. **Replaced `NOT IN` with `LEFT JOIN IS NULL`** — avoids O(n²) scan behavior

## Rewritten SQL

```sql
-- OPT: promoted repeated subquery to CTE
WITH user_events AS (
  SELECT user_id, event_type, event_date
  FROM `{project}.{dataset}.events`
  WHERE event_date BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) AND CURRENT_DATE()
  -- OPT: added partition filter
),

...

SELECT ...
```

## Unchanged Behavior

- Output columns: {list} — identical to original
- Row grain: one row per {grain}
- Filters: all original filters preserved

## Notes

- {any judgment calls: why a specific pattern was or wasn't changed}
- {any approximation functions considered but not applied}
```

---

## Escalation

> "Halt. The proposed rewrite changes the output: original returns {X} columns,
> rewrite returns {Y}. Cannot confirm semantic equivalence — returning original SQL
> with the diagnosis only."

> "Halt. After revision, rewrite is still blocked by guardrail: {reason}. Review
> the original SQL for structural issues before optimizing."

---

## Upstream Skills

- `sql_builder` → if the SQL being optimized was machine-generated
- `bq_schema_probe` → schema intake for partition/join analysis
- `bq_query_guardrail` → validates every rewrite (invoked inline)

## Downstream Skills

- `lookml_view_reviewer` → if the optimized SQL is being promoted to LookML
- `grain_validator` → if JOIN behavior changed during optimization
