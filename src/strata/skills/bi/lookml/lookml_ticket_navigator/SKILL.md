# Skill: lookml_ticket_navigator

domain: bi/lookml
mode: navigate
complexity: low
version: 0.2.0

> Given a ticket anchor (BQ table, field name, explore, view, or .lkml file), get a
> complete navigator brief in **one tool call** — the structured context a downstream skill
> or developer needs to act without exploring the repo blind.

---

## Trigger

- Starting a ticket that touches LookML or a BQ table
- "Where does X live in the repo?"
- "What already exists for field / table / explore Y?"
- Before running `lookml_view_reviewer` or `lookml_explore_join_reviewer`
- Any time an agent would otherwise explore `.lkml` files blind

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `anchor` | yes | human / ticket | BQ table name, field name, explore name, view name, or `.lkml` filename |
| `ticket_text` | no | human | Jira/GitHub ticket description — used to infer change type |
| `model` | no | human | Model name to narrow scope (omit to search full repo) |

---

## Allowed Tools

- `strata_mcp.strata_navigate` — **primary.** Classifies the anchor and returns the full brief
  (views, explores, fields, `source_file:source_line` citations, change type, what-to-touch).
- `strata_mcp.strata_query_field` — optional deep-dive on a single field from the brief.
- `strata_mcp.strata_ir_status` — stop-condition / status check.
- file read: `.lkml` source files at the `file:line` citations the brief returns (targeted, read-only).

> One `strata_navigate` call replaces hand-orchestrating `strata_impact`, `strata_find_field`,
> `strata_view_sources`, and `strata_explore_deps`. Do not re-derive the brief by calling those
> primitives in a loop — that is the token-heavy path this skill exists to avoid.

---

## Forbidden

- Do not modify any LookML file
- Do not execute any BQ queries
- Do not call `bq_schema_probe` — that belongs to the downstream skill
- Do not call `lookml_view_reviewer` or `lookml_explore_join_reviewer` — hand off to those
- Do not loop over the IR primitives to rebuild what `strata_navigate` already returns

---

## Procedure

**Step 1 — Pick the anchor from the ticket**

From `ticket_text`, identify the single best anchor to investigate:
- A BQ table named in the ticket → use the fully-qualified `project.dataset.table`
- A field/metric named → use `field_name` (or `view.field` if the view is known)
- An explore or view named → use that name
- A file named → use the `.lkml` filename

If the ticket names several, pick the most specific one; you can run a second pass for others.
Pass `model` only if the ticket scopes the work to one model.

**Step 2 — One navigate call**

Call `strata_mcp.strata_navigate(anchor, model, ticket_text)`.

The returned brief contains, as applicable:
- `anchor_type` — how the anchor was classified
- `views` / `backing_tables` — name, `physical_table`, `field_count`, `source_file`, `source_line`
- `explores` — name, `base_view`, `field_count`, `joins`, `source_file`, `source_line`
- `field_matches` — view, field, type, `source_file`, `source_line` (field anchors)
- `bq_fields` — fields on the table (BQ-table anchors)
- `change_type` + `what_to_touch` — when `ticket_text` was provided
- `truncated` — set when results were capped (re-run with a `model` filter)

If the brief has an `error` key → halt and report it verbatim (e.g. anchor not found —
suggest checking spelling or running `strata query status`).

**Step 3 — Optional deep-dive**

If the change centers on one field, call `strata_query_field(view, field)` for the top match
to get its full SQL / type / tags. Skip this unless the ticket needs field-level detail.

**Step 4 — Read only what you must**

If you need the surrounding LookML, open the exact `source_file:source_line` the brief cites —
never scan whole files blind.

**Step 5 — Emit the navigator brief**

Format the tool output as the markdown below. Carry the `file:line` citations through so every
target is clickable, and lead with the `what_to_touch` list when a change type was inferred.

---

## Output Format

```markdown
## Navigator Brief — `{anchor}`

**Anchor type:** {bq_table | field | explore | view | file}
**Change type:** {add_field | add_join | new_view | rename | drop | unknown}

## What to Touch

1. **{action}** → `{file:line}` — {reason}
2. ...

## Relevant LookML Nodes

| Node | Kind | Source | Physical Table |
|---|---|---|---|
| `orders` | view | `views/orders.view.lkml:1` | `project.dataset.orders` |
| `order_items` | explore | `models/ecommerce.model.lkml:43` | — |

## Join Graph (affected explores)

- `order_items` (ecommerce): base=`orders` → joined: [users, inventory_items]

## Field Matches (field anchor only)

- `orders.lifetime_value` — measure · `views/orders.view.lkml:88`

## Hand-off

→ `lookml_view_reviewer` on `{view}` — before deploying any field change
→ `lookml_explore_join_reviewer` on `{explore}` — if a join is new or modified
→ `bq_schema_probe` on `{physical_table}` — if you need schema/grain info

> Truncation: {brief.truncated, if present}
```

---

## CLI fast-path (terminal-capable agents only)

**Prefer the `strata_navigate` MCP tool** — it already has the repo configured, so it is one call
with no setup. Use the CLI only if the MCP tool is unavailable, and always pass `--repo` (or set
`STRATA_REPO_PATH`): a shell does not inherit the MCP server's environment, so without it the
command has no repo and will fail. Do not fall back to reading `.lkml` files blind.

```bash
strata skill list                          # discover skills from the shell
strata skill lookml_ticket_navigator       # read this procedure from the shell

# --repo is REQUIRED unless STRATA_REPO_PATH is exported in this shell
strata query navigate "{anchor}" --repo "{repo_path}" --ticket "{ticket_text}" --out brief.md
strata query navigate "{anchor}" --repo "{repo_path}" --json
```

---

## Stop Conditions

- Brief returns an `error` key → halt, report it with the suggested fix
- `strata_ir_status` shows 0 nodes → halt: "IR appears empty — run `strata build` first"

---

## Examples

See `examples/` for sample inputs and outputs.

---

## Escalation

> "Halt. Anchor `{anchor}` matches more explores than a safe brief can cover (`truncated` set).
> Provide a `model=` filter or a more specific anchor."
