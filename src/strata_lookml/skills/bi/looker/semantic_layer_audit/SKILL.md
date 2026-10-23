# Skill: semantic_layer_audit

domain: bi/looker
mode: audit
complexity: high
version: 0.1.0

> Full health check of a Looker semantic layer: dead explores, orphaned views,
> schema drift hits, PDT debt, and join risk surface. Produces a prioritized
> remediation backlog. Entry point for quarterly governance reviews.

---

## Trigger

- Quarterly governance review
- After a warehouse migration (table renames, schema changes)
- Dead code register has grown by > 20% since last audit
- Onboarding to a new Looker instance — first-pass health check

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `model` | no | human | Scope audit to one model (omit for all models) |
| `drift_threshold` | no | config | Drift hit count that triggers HIGH risk label (default: 5) |

---

## Allowed Tools

- `strata_mcp.strata_ir_status` — repo overview, node counts
- `strata_mcp.strata_usage_summary` — L1 data availability, query volume
- `strata_mcp.strata_dead_code_register` — full dead explore + zombie view list
- `strata_mcp.strata_schema_drift` — column-level drift hits
- `strata_mcp.strata_pdt_costs` — PDT build ledger, unused PDTs
- `strata_mcp.strata_list_orphans` — orphaned views and fields
- `strata_mcp.strata_explore_deps` — per-explore join graph (for flagged explores)

---

## Forbidden

- Do not modify any LookML or BQ resources
- Do not post results anywhere without human approval
- Do not run `lookml_explore_join_reviewer` on every explore — only flag HIGH RISK candidates

---

## Procedure

1. `strata_ir_status` → node counts, cache age. Flag stale cache (> 24h) as caveat.
2. `strata_usage_summary` → confirm L1 data present. If `has_l1: false` → note limited visibility (no usage data).
3. `strata_dead_code_register` → count dead explores, zombie views. Compute % of total explores.
4. `strata_schema_drift` → group drift hits by view. Flag views with > `drift_threshold` hits as HIGH RISK.
5. `strata_pdt_costs` → count unused PDTs and estimated build cost.
6. `strata_list_orphans` → count orphaned views and fields.
7. `[JUDGMENT]` Dead explore rate > 30% → flag as CRITICAL (semantic layer significantly overgrown).
8. `[JUDGMENT]` For each HIGH RISK drift view: does it back a dead or live explore? Live + drifted = most urgent.
9. Produce risk surface table ranked by severity.
10. Produce remediation backlog as ordered checklist — highest business impact first.

---

## Stop Conditions

- IR not built (no cache, no repo path) → halt, instruct on `make ci`
- L1 not available and model not specified → proceed with caveat, note all dead code findings are structural only (no usage evidence)

---

## Output Format

```markdown
## Semantic Layer Audit — {repo} ({date})

**Model scope:** {model or "all"}
**IR built at:** {timestamp}
**L1 data:** available / not available

---

## Risk Surface

| Area | Count | Severity |
|---|---|---|
| Dead explores | {n} ({pct}% of total) | HIGH / MEDIUM / LOW |
| Zombie views | {n} | HIGH / MEDIUM |
| Schema drift hits | {n} ({views} views affected) | HIGH / MEDIUM |
| Unused PDTs | {n} | MEDIUM |
| Orphaned views | {n} | LOW |
| Orphaned fields | {n} | LOW |

---

## Top Findings

### CRITICAL
- [ ] {finding with explore/view name and specific evidence}

### HIGH
- [ ] {finding}

### MEDIUM
- [ ] {finding}

---

## Remediation Backlog

1. **[Explore name]** — dead, {n} zombie views depend on it. Run `lookml_explore_join_reviewer` then archive.
2. **[View name]** — {n} drift hits, backs live explore `{explore}`. Run `lookml_view_reviewer`.
3. **[PDT name]** — unused for {n} days, costs ~{estimate}. Safe to drop.

---

## Suggested Next Skills
- `lookml_explore_join_reviewer` on: {list of flagged explores}
- `lookml_view_reviewer` on: {list of drift-hit views}
- `bq_schema_probe` on: {tables with highest drift counts}
```

---

## Escalation

> "Audit complete. {n} critical findings require human review before any remediation
> begins. Post this report to the team before actioning the backlog."

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
