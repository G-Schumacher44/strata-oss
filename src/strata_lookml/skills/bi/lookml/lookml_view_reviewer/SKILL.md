# Skill: lookml_view_reviewer

domain: bi/lookml
mode: audit
complexity: medium
version: 0.1.0

> Audit a LookML view for correctness, safety, and maintainability issues.
> Catches SQL injection vectors, unbounded measures, missing primary keys,
> and inheritance chains that will break at query time.

---

## Trigger

- New view file added in a PR
- Existing view flagged in schema drift report
- `strata_validation_scope` returns a view as impacted by a changed table
- Refactor of a view referenced by high-traffic explores

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `view` | yes | human | View name |
| `source_file` | no | strata_mcp | Path to `.lkml` file — derived from IR if omitted |

---

## Allowed Tools

- `strata_mcp.strata_query_field` — inspect individual field SQL and tags
- `strata_mcp.strata_explore_deps` — find explores that reference this view
- `strata_mcp.strata_dead_code_register` — check if view or its explores are dead
- `strata_mcp.strata_impact` — get all fields and explores impacted by this view's table
- file read: view `.lkml` source file

---

## Forbidden

- Do not modify any LookML file
- Do not execute queries

---

## Procedure

1. Resolve source file from IR or `source_file` input — read the full file
2. Check `sql_table_name` or `derived_table`: confirm physical table or SQL is present
3. Check `primary_key: yes` declared on exactly one dimension — flag missing PK as **HIGH RISK**
4. Scan all `sql:` fields:
   - Liquid template injection: `${parameter_name}` in SQL without a `required_access_grants` or type constraint → flag **SECURITY**
   - `${TABLE}` substitution present and correct → OK
   - Raw SQL string literals (no `${}` reference) in measures → flag **HARDCODED SQL**
5. Check measures: any `type: sum` or `type: average` without a `filters:` or clear scope → flag **UNBOUNDED MEASURE**
6. Check `extends:` chain: if present, resolve parent views from IR — flag broken chain (parent not in IR)
7. Check `refinements` (`+view_name`): confirm base view exists
8. `[JUDGMENT]` Tag coverage: fields with no `tags:` on a view > 20 fields → flag **LOW OBSERVABILITY**
9. Check if view appears in dead code register — flag prominently
10. List explores that reference this view (from `strata_explore_deps` or IR traversal)

---

## Stop Conditions

- View not found in IR and source file path not provided → halt, ask for file path
- Source file unreadable → halt, report

---

## Output Format

```markdown
## View Review — `{view}`

**Source:** {file}
**Table:** {sql_table_name}
**Extends:** {parent or none}
**Explores referencing this view:** {list}
**Dead code flag:** YES / NO

## Findings

### SECURITY
- [ ] Field `{name}`: liquid parameter `{param}` used in SQL without type constraint

### HIGH RISK
- [ ] No `primary_key: yes` declared — Looker cannot enforce join uniqueness

### UNBOUNDED MEASURES
- [ ] `{measure}`: type sum with no filter — will sum across all rows in any explore context

### OK
- [x] PK declared on `{field}`
- [x] All sql: fields use ${TABLE} substitution

## Verdict
PASS / NEEDS REVIEW / HIGH RISK

## Recommended Actions
1. [Specific fix for highest-severity finding]
```

---

## Escalation

> "Halt. View `{view}` uses a liquid parameter `{param}` in a `sql:` field without
> a type constraint. This is a SQL injection vector. Do not deploy until the field
> is restricted to `type: string` with an `allowed_values` list or replaced with
> a safe templated filter."

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
