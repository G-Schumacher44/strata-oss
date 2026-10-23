# Skill: lookml_explore_join_reviewer

domain: bi/lookml
mode: audit
complexity: medium
version: 0.1.0

> Audit an explore's join graph for fanout risk, missing relationship declarations,
> and dead joins. Surfaces the joins most likely to produce wrong numbers before
> a user ever runs a query.

---

## Trigger

- New explore added to a model
- A metric unexpectedly doubles or inflates after a join
- Code review of a LookML PR touching an explore
- `semantic_layer_audit` flags an explore for join review

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `explore` | yes | human | Explore name |
| `model` | yes | human | Model name |

---

## Allowed Tools

- `strata_mcp.strata_explore_deps` — get join list, base view, field count
- `strata_mcp.strata_dead_code_register` — check if explore or joined views are dead
- `strata_mcp.strata_ir_status` — confirm model exists in IR
- file read: explore `.lkml` source file for raw join declarations

---

## Forbidden

- Do not modify any LookML file
- Do not execute queries against Looker or BQ
- Do not flag stylistic issues — fanout and correctness only

---

## Procedure

1. `strata_mcp.strata_explore_deps(explore, model)` → get base view, joins, field count
2. Check explore in dead code register — if present, flag prominently and continue (audit still useful)
3. For each join: read the raw join block from the source `.lkml` file
4. Check `relationship:` declared on every join — flag any missing as **HIGH RISK**
5. Check `many_to_many` or `many_to_one` joins without a `sql_where:` or `fields:` constraint → flag as **FANOUT RISK**
6. Check for joins on the same view appearing more than once under different aliases → flag as **ALIAS AMBIGUITY**
7. `[JUDGMENT]` Identify join chains longer than 3 hops — flag as **COMPLEXITY RISK** (harder to reason about fanout)
8. Check for joined views with 0 fields in the explore's `fields:` list → flag as **DEAD JOIN**
9. Check if any joined view appears in the dead code register → flag as **DEAD VIEW JOIN**
10. Produce findings list ranked by severity

---

## Stop Conditions

- Explore not found in IR → halt, report
- Model not found → halt, report

---

## Output Format

```markdown
## Explore Join Review — `{model}.{explore}`

**Base view:** {view}
**Joins:** {n}
**Field count:** {n}
**Dead code flag:** YES / NO

## Findings

### HIGH RISK
- [ ] Join `{name}`: missing `relationship:` declaration — fanout type unknown

### FANOUT RISK
- [ ] Join `{name}`: `many_to_one` with no field constraint — all {view} fields exposed, join may inflate {base_view} rows

### DEAD JOINS
- [ ] Join `{name}`: view `{view}` has 0 fields in explore — join fires but returns nothing useful

### OK
- [x] Joins with correct `relationship:` and appropriate `fields:` constraints

## Verdict
PASS / NEEDS REVIEW / HIGH RISK

## Recommended Actions
1. [Specific fix for highest-severity finding]
```

---

## Escalation

> "Halt. Explore `{model}.{explore}` has {n} joins with missing `relationship:`
> declarations. Queries against this explore may silently produce inflated numbers.
> Do not deploy until relationship types are declared."

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
