# Skill: bi_incident_responder

domain: bi/delivery
mode: audit
complexity: high
version: 0.1.0

> Structured first-response for a broken dashboard or wrong number report.
> Separates data quality issues from LookML bugs from PDT failures.
> Produces a root cause hypothesis and next action — not a fix.

---

## Trigger

- "This dashboard is showing wrong numbers"
- "This explore stopped working"
- "Users report metric X dropped to zero / spiked unexpectedly"
- Looker content alert fires

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `symptom` | yes | human | Plain-language description of what's wrong |
| `explore` | no | human | Explore or dashboard name if known |
| `model` | no | human | Model name if known |
| `affected_metric` | no | human | The metric that looks wrong |
| `time_of_change` | no | human | When the issue was first noticed |

---

## Allowed Tools

- `strata_mcp.strata_dead_code_register` — check if flagged explore is dead
- `strata_mcp.strata_schema_drift` — check for recent column drops in relevant views
- `strata_mcp.strata_pdt_costs` — check PDT build status
- `strata_mcp.strata_explore_deps` — get join graph for the explore
- `strata_mcp.strata_impact` — trace which views and explores back a changed table

---

## Forbidden

- Do not modify any LookML, BQ tables, or PDTs
- Do not run BQ queries (use `bq_schema_probe` or `bq_query_guardrail` as sub-skills if needed)
- Do not post findings to stakeholders without human approval

---

## Procedure

1. Restate the symptom in one sentence — confirm understanding with the reporter if ambiguous
2. `strata_dead_code_register` → is the named explore dead? If yes → likely the root cause
3. `strata_schema_drift` → any drift hits on views backing the explore? Match to `time_of_change` if provided
4. `strata_pdt_costs` → any PDTs in `failed` or `building` state? PDT failure is a common zero-metric cause
5. `strata_explore_deps(explore, model)` → inspect join graph — flag any `many_to_many` joins as fanout candidates
6. `[JUDGMENT]` Classify symptom type:
   - **Zero / null**: PDT failed, column dropped, explore dead, filter too narrow
   - **Inflated**: join fanout, missing dedup, grain mismatch
   - **Stale**: PDT not rebuilt, cache serving old data
   - **Broken UI**: LookML parse error, field reference invalid
7. Form 1–3 hypotheses ranked by likelihood given evidence
8. For each hypothesis: state the one diagnostic step that would confirm or rule it out
9. Output incident brief — do not attempt fixes

---

## Stop Conditions

- Symptom is too vague to classify → halt, ask reporter for: (1) specific metric name, (2) expected vs actual value, (3) when it changed
- No explore or model named and IR has > 10 explores → halt, ask which explore the dashboard uses

---

## Output Format

```markdown
## Incident Brief — {symptom summary}

**Reported:** {time_of_change or "unknown"}
**Scope:** {explore or "unknown"} / {affected_metric or "unknown"}
**Symptom type:** Zero / Inflated / Stale / Broken UI

---

## Evidence

| Check | Result |
|---|---|
| Explore in dead code register | YES / NO |
| Schema drift hits on backing views | {n} hits / none |
| PDT build status | OK / FAILED / BUILDING |
| Join graph risk | {highest-risk join or "none flagged"} |

---

## Hypotheses (ranked)

1. **[Most likely]:** {hypothesis} — evidence: {what supports it}
2. **[Second]:** {hypothesis} — evidence: {what supports it}

---

## Next Diagnostic Steps

1. To confirm hypothesis 1: {single action — bq query, PDT log check, LookML read}
2. To confirm hypothesis 2: {single action}

---

## Suggested Next Skill
`{skill_name}` — because {one sentence}
```

---

## Escalation

> "Halt. Cannot diagnose without more information. Ask the reporter:
> (1) What is the exact metric name and dashboard?
> (2) What value did you expect vs. what did you see?
> (3) Did this work yesterday, or has it never worked?"

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
