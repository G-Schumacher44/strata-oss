# Skill: chart_composer

domain: bi/visualization
mode: draft
complexity: low
version: 0.1.0

> Produce a polished, interactive chart from a business question and a data source.
> Meeting-ready in under 60 seconds. Works agentically or by hand via CLI.

---

## Trigger

- "Can you show me X as a chart?"
- "I need a quick viz for my meeting"
- Stakeholder asks for a one-off visualization
- Output of `bq_schema_probe` or a BQ query result needs a visual

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `question` | yes | human | What does the chart need to answer? |
| `data` | yes | human / BQ / strata_mcp | JSON rows or CSV — the data to plot |
| `out_path` | no | human | Where to save the HTML (default: /tmp/strata_chart.html) |

---

## Allowed Tools

- `strata_mcp.strata_chart_templates` — list available chart types
- `strata_mcp.strata_render_chart` — render spec + data → HTML file
- `bq_query_guardrail` (sub-skill) — if data needs a BQ query first

**By hand (CLI):**
```bash
make chart-list                          # see available types
make chart TYPE=bar DATA=data.json       # render + open in browser
make chart-save TYPE=line DATA=data.csv OUT=/tmp/trend.html
strata-chart bar data.json --title "Revenue by Region" --open
```

---

## Forbidden

- Do not invent column names — only use columns present in the data
- Do not run BQ without `bq_query_guardrail`
- Do not render without confirming the output path is acceptable

---

## Procedure

1. Classify the question type:
   - Comparison across categories → `bar`
   - Trend over time → `line`
   - Correlation between measures → `scatter`
   - Two-dimensional breakdown → `heatmap`

2. `strata_chart_templates()` → confirm chosen type is available

3. Map data columns to spec fields:
   - `x.field`: the categorical or date column
   - `y.field`: the quantitative column (the metric)
   - `color.field`: optional — use for grouping or multi-series

4. Set `title` to a plain-language description of the question

5. `[JUDGMENT]` Set `x.title` / `y.title` if column names are unclear
   (e.g. `dim_region` → title: "Region"). Skip if column names are already readable.

6. Set `show_labels: true` if the chart will be read in a presentation context
   (bar/point charts only)

7. Build the spec as a YAML string — fill all REQUIRED fields, omit empty OPTIONAL fields

8. `strata_render_chart(spec_yaml, data_json, out_path)` → get file path

9. Report the path. If the agent has browser access, open it.

10. Adjustments: modify spec fields only and re-render — never re-query the data

---

## Stop Conditions

- Data has no columns that match the question → halt, ask for the right data
- Question type is ambiguous between two chart types → ask which framing is more useful
- No data provided and BQ query needed → invoke `bq_query_guardrail` first

---

## Output Format

```markdown
## Chart: {title}

**Type:** {bar|line|scatter|heatmap}
**File:** {out_path}

### Spec used
```yaml
{filled spec}
```

Open {out_path} in a browser to view. To adjust: tell me which field or label to change.
```

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
