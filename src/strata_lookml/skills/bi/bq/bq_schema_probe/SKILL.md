# Skill: bq_schema_probe

domain: bi/bq
mode: audit
complexity: low
version: 0.1.0

> Inspect one or more BigQuery tables before writing any SQL. Produces a structured
> intake report that feeds downstream skills (SQL drafting, LookML generation, join
> validation, dashboard planning).

---

## Trigger

- Before writing any SQL that touches an unfamiliar table
- Before generating LookML from a BQ source
- When `jira_to_bi_spec` identifies required data sources
- Before `grain_validator` or `bq_query_guardrail`

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `table_refs` | yes | human / jira ticket | Fully-qualified BQ table names (`project.dataset.table`) |
| `bq_project` | no | gcloud default project; override via `~/.strata/config.json` → `bq_project` or `STRATA_BQ_PROJECT` | Only needed if `table_refs` use 2-part names (`dataset.table`); 3-part names are self-contained |
| `question` | no | human | Business question being answered — shapes grain guess |

---

## Allowed Tools

- `bq_cli`: `bq show --schema`, `bq query --dry_run`, `bq query` (SELECT only, LIMIT 5)
- `strata_mcp.strata_schema_drift` — cross-reference known drift hits
- file read: `.strata`, `tests/fixtures/` schema JSONs

---

## Forbidden

- No BQ writes (INSERT, UPDATE, DELETE, CREATE, DROP)
- No queries without LIMIT clause
- Do not infer business meaning from column names alone — flag ambiguity explicitly

---

## Procedure

1. For each `table_ref`, run: `bq show --schema --format=prettyjson project.dataset.table`
2. Parse schema → extract: column names, types, modes (NULLABLE/REQUIRED/REPEATED)
3. Identify candidate primary keys: columns named `*_id`, `*_key`, or REQUIRED + STRING/INT
4. Identify date/timestamp fields: types DATE, DATETIME, TIMESTAMP
5. Identify partition field: check `bq show --format=prettyjson` for `timePartitioning`
6. `[JUDGMENT]` Guess grain: based on candidate PKs + question context, state the most likely grain in one sentence. Flag if uncertain.
7. For each pair of tables in `table_refs`: identify join candidates (shared column names + compatible types)
8. Check `strata_mcp.strata_schema_drift` for any drift hits on these tables — surface warnings
9. Run `SELECT * FROM table LIMIT 5` for each table — note NULL density, value patterns, date range
10. Assemble output report

---

## Stop Conditions

- Table not found → halt, report exact ref that failed, ask human to confirm name
- Schema returns 0 columns → halt, may be a view or access issue
- `[JUDGMENT]` grain is ambiguous between two equally plausible keys → halt, list both options, ask human

---

## Output Format

```markdown
## Tables Inspected
- `project.dataset.table` — N columns, partitioned on `date_col` / not partitioned

## Grain Guess
One sentence. Confidence: high / medium / low.
[If low: state the two competing interpretations]

## Candidate Primary Keys
- `col_name` — reason

## Date Fields
- `col_name` — type, range from sample (YYYY-MM-DD to YYYY-MM-DD)

## Join Candidates
- `table_a.col` ↔ `table_b.col` — type match, estimated cardinality

## Partition / Clustering
- Partition: `col_name` (DAY/MONTH) or none
- Clustering: `col_name, col_name` or none

## Schema Drift Warnings
- [from strata_mcp] or "none detected"

## Risk Notes
- NULL density issues, unexpected types, wide tables (>100 cols), REPEATED fields
```

---

## Escalation

> "Halt. Table `[ref]` could not be resolved. Confirm the fully-qualified name
> (`project.dataset.table`) and that your ADC credentials have read access."

> "Halt. Grain is ambiguous between `[key_a]` (suggesting row = X) and `[key_b]`
> (suggesting row = Y). Which is the intended grain for this analysis?"

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
