# Skill: [skill_name]

domain: bi/bq | bi/lookml | bi/looker | bi/visualization | bi/delivery | governance
mode: audit | draft | validate | patch
complexity: low | medium | high
version: 0.1.0

> One sentence. What does this skill do and when would you reach for it?

---

## Trigger

When should an agent invoke this skill? Be specific — a cheap model needs a clear signal.

Examples:
- "Before writing any SQL against an unfamiliar table"
- "When a KPI dashboard tile shows unexpected movement"
- "When a Jira ticket contains a BI request"

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `input_name` | yes/no | `tool_name` / human / prior skill output | what it is |

---

## Allowed Tools

List exactly. Cheap models must not reach for tools not listed here.

- `strata_mcp.*` — which tools
- `bq_cli` — which subcommands
- `looker_mcp.*` — which tools
- `jira_mcp.*` — which tools (stub: requires Jira MCP configured)
- file read — which paths

---

## Forbidden

Hard stops. Non-negotiable.

- No writes to LookML files
- No BQ queries without dry-run guard first
- No Looker API writes
- [skill-specific additions]

---

## Procedure

Numbered steps. Cheap model executes top to bottom. No reasoning required between steps unless explicitly marked `[JUDGMENT]`.

1. Step one
2. Step two
3. `[JUDGMENT]` — step where model must reason (keep these rare and bounded)
4. Step four

---

## Stop Conditions

When to halt and surface to a human instead of continuing.

- Required input missing and cannot be inferred
- Dry-run cost exceeds threshold
- Ambiguous grain — two plausible interpretations
- [skill-specific conditions]

---

## Output Format

```markdown
## [Section heading]
[content]

## [Section heading]
[content]
```

---

## Escalation

What to do when a stop condition is hit. Be explicit — a cheap model needs a script.

> "Halt. State: [what you found]. Ask: [specific question to resolve the ambiguity]."

---

## Examples

- `examples/good_input.md` — a realistic input that produces clean output
- `examples/good_output.md` — the expected output for that input
