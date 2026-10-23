# Skill: dashboard_composer

domain: bi/visualization
mode: draft
complexity: medium
version: 0.1.0

> Turn a business ask into a filled dashboard config, ready for Looker MCP to
> create. Template selection and layout decisions are pre-encoded — the agent
> fills in data fields only. Polished visual output from a lightweight model.

---

## Trigger

- "Build me a dashboard for X"
- Output of `jira_to_bi_spec` contains a dashboard deliverable
- Output of `looker_dashboard_builder_plan`
- Stakeholder request with an identified explore

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `business_ask` | yes | human / jira_to_bi_spec | What question the dashboard answers |
| `audience` | yes | human / jira_to_bi_spec | `executive` / `operational` / `analytical` |
| `explore` | yes | human / strata_mcp / looker_mcp | Explore name to build against |
| `model` | yes | human / strata_mcp | Looker model name |
| `primary_metric` | no | human | If known upfront — skips field selection step |

---

## Allowed Tools

- `strata_mcp.strata_explore_deps` — get available fields from the explore
- `strata_mcp.strata_dead_code_register` — check if explore is live
- `looker_mcp.get_explore_fields` — get full field list with labels
- `looker_mcp.create_dashboard` — final creation step
- `looker_mcp.create_look` — for individual tiles if needed
- file read: `skills/bi/visualization/templates/`

---

## Forbidden

- Do not invent field names — every field in the config must be confirmed in the explore
- Do not modify template structure (layout, chart types, color rules) — fill `REQUIRED` fields only
- Do not create explores or modify LookML
- Do not call `looker_mcp.create_dashboard` until all REQUIRED fields are filled and validated

---

## Procedure

1. Check explore is live: `strata_mcp.strata_dead_code_register` → if explore appears, **HALT** (dead code warning)
2. Get available fields: `strata_mcp.strata_explore_deps(explore, model)` → note measures and dimensions
3. Select template based on audience:
   - `executive` → `executive_kpi_v1`
   - `operational` → `operational_monitor_v1`
   - `analytical` → `trend_analysis_v1` (default if uncertain)
4. Read the selected template file from `skills/bi/visualization/templates/`
5. Fill all `REQUIRED` fields from the available field list:
   - Primary measure: the field that most directly answers `business_ask`
   - Time dimension: the most relevant date/timestamp field
   - Breakdown dimension: highest-cardinality categorical that segments the primary metric
6. Fill `OPTIONAL` fields where a strong candidate exists — skip if uncertain
7. `[JUDGMENT]` If no field clearly maps to a REQUIRED slot → stop condition
8. Validate: every filled field name exists in the explore's field list
9. Produce filled config as output artifact
10. Ask human to approve before calling `looker_mcp.create_dashboard`

---

## Stop Conditions

- Explore is in dead code register → halt, surface warning, ask if they mean a different explore
- No field matches a REQUIRED slot after reviewing all available fields → halt, list what's missing
- Audience is unclear between executive and analytical → ask before template selection
- Human approval not given → do not call `create_dashboard`

---

## Output Format

```markdown
## Dashboard Plan

**Template:** executive_kpi_v1
**Explore:** model_name.explore_name
**Audience:** Executive

### Filled Config
[YAML block with all REQUIRED fields populated, OPTIONAL fields filled or marked omitted]

### Field Mapping
| Template slot | Field used | Why |
|---|---|---|
| primary_kpi.measure | orders.total_revenue | Directly answers "revenue performance" |
| trend.time_dimension | orders.created_date | Primary date dimension in explore |
| breakdown.dimension | orders.region | Highest-value categorical for revenue breakdown |

### Fields Left as OPTIONAL (omitted)
- secondary_kpi: no clear secondary metric identified
- dimension_filter: no obvious segmentation filter needed

### Ready to create?
Respond YES to call `looker_mcp.create_dashboard` with this config.
```

---

## Escalation

> "Halt. The explore `[name]` appears in the dead code register with 0 queries
> over 30 days. Confirm this is the right explore, or specify an alternative."

> "Halt. No field in `[explore]` maps clearly to the primary measure slot.
> Available measures: [list]. Which should be the hero metric?"

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
