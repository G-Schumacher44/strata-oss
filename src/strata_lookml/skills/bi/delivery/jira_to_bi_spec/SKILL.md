# Skill: jira_to_bi_spec

domain: bi/delivery
mode: draft
complexity: medium
version: 0.1.0

> Convert a messy Jira ticket into an executable BI work spec. Separates business
> intent from technical plan. Output feeds directly into build skills
> (dashboard_composer, lookml_view_reviewer, build_looker_feature).

requires:
  - jira_mcp  # stub: configure Jira MCP in your MCP client before using

---

## Trigger

- A Jira ticket is assigned to the BI team
- Stakeholder drops a ticket link into chat
- Sprint planning — convert backlog items to actionable specs

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `ticket_id` | yes | human | Jira ticket ID (e.g. `DATA-142`) |
| `repo_context` | no | strata_mcp | Current IR state for field/explore suggestions |

---

## Allowed Tools

- `jira_mcp.get_issue` — fetch ticket title, description, comments, attachments
- `jira_mcp.get_issue_comments` — fetch full comment thread
- `jira_mcp.create_issue` — create child/linked spec ticket (with approval)
- `jira_mcp.add_comment` — post spec back to original ticket (with approval)
- `strata_mcp.strata_ir_status` — check available explores and models
- `strata_mcp.strata_explore_deps` — suggest relevant explores
- `strata_mcp.strata_dead_code_register` — flag if suggested explore is dead

---

## Forbidden

- Do not create or update Jira issues without explicit human approval
- Do not assume business definitions — flag every ambiguous term explicitly
- Do not invent data sources — only suggest sources visible in the IR or explicitly named in the ticket

---

## Procedure

1. Fetch ticket: `jira_mcp.get_issue(ticket_id)` → title, description, reporter, priority
2. Fetch comments: `jira_mcp.get_issue_comments(ticket_id)` → full thread
3. Extract business ask: one sentence, no jargon, in the reporter's words
4. Identify named data sources: table names, dashboard names, explores, metrics mentioned in ticket
5. `[JUDGMENT]` Flag ambiguous terms: metric names with multiple plausible definitions, date ranges without clear boundaries, "all data" requests without specified scope
6. Check IR for relevant explores: `strata_mcp.strata_ir_status` + `strata_mcp.strata_explore_deps` for each named source
7. Flag dead explores: `strata_mcp.strata_dead_code_register` — warn if a named explore is dead
8. Draft acceptance criteria: 3-5 specific, testable conditions (not "looks right")
9. Draft technical plan: ordered list of skills to invoke (bq_schema_probe → dashboard_composer → etc.)
10. List open questions: anything that blocks starting work
11. Output spec — do not post to Jira until human approves

---

## Stop Conditions

- Ticket description is fewer than 2 sentences with no attachments → halt, ask reporter for more context via escalation script
- Business ask has more than one plausible interpretation → halt, list interpretations, ask human to pick
- Required data source does not exist in IR and is not a known BQ table → halt, flag as blocker

---

## Output Format

```markdown
## BI Work Spec — [TICKET_ID]: [Ticket Title]

**Reporter:** name
**Priority:** P1 / P2 / P3
**Original ask:** (verbatim quote from ticket)

---

## Business Ask
One sentence. Plain language. No acronyms.

## Data Sources
- `project.dataset.table` or `model.explore` — why it's relevant
- [flag if dead or missing]

## Definitions Needed
- **[Term]:** ambiguous — could mean X or Y. [JUDGMENT REQUIRED]

## Assumptions
- Date range: [what we're assuming and why]
- Grain: [row = one X]
- Scope: [what's included / excluded]

## Acceptance Criteria
- [ ] [Specific, testable condition]
- [ ] [Specific, testable condition]
- [ ] Numbers validated against [source]

## Technical Plan
1. `bq_schema_probe` on [tables]
2. `[next skill]`
3. Human review of output before delivery

## Open Questions
- [Blocking question that must be answered before work starts]

## Suggested Next Skill
`[skill_name]` — because [one sentence reason]
```

---

## Escalation

> "Halt. Ticket `[ID]` does not contain enough detail to spec. Post to Jira:
> 'To start this work we need: (1) which metric defines success, (2) which time
> period, (3) who is the primary audience for the output.'"

> "Halt. The explore `[name]` mentioned in this ticket has 0 queries over 30 days
> and is flagged as dead code. Confirm with reporter whether this is the right source."

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
