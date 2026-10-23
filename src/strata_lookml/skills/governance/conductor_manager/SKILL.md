# Skill: conductor_manager

domain: governance
mode: draft
complexity: medium
version: 0.1.0

> Manage the Conductor workflow by scaffolding slices, bounding scope, and maintaining index.md

---

## Trigger

- "Start a new slice for..."
- "Help me plan a cross-cutting change"
- "Update the active slice"

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `objective` | yes | human | What problem needs solving |
| `mode` | yes | human/inferred | patch / slice / full / audit |
| `budget` | no | inferred | Expected context spend (low/medium/high) |

---

## Allowed Tools

- `run_shell_command`: `strata conductor new-slice`
- `read_file` / `write_file` / `replace` for modifying `conductor/index.md`

---

## Forbidden

- Do not write implementation code in the same turn you draft the slice. "Spec Before Build."
- Do not span multiple architectural layers in a single slice unless mode is `full`.

---

## Procedure

1. If the user hasn't provided clear requirements, ask clarifying questions.
2. Run `strata conductor new-slice "<title>"` with appropriate `--mode` and `--budget` flags.
3. `[JUDGMENT]` Review the generated `conductor/slice-*.md` file. Add a precise "Objective", "Scope", and "Implementation Order".
4. `[JUDGMENT]` Define the "Hard Constraint" - what must be true for correctness before any downstream work is trusted.
5. Append the newly created slice to the `## Phase Status` tracking table in `conductor/index.md`.
6. Update `conductor/index.md` to set `Active slice:` to the new file.
7. Output the drafted slice to the user for review.

---

## Stop Conditions

- User requirements are too vague to determine which layer the change belongs in.
- The change spans more than one architectural layer and `full` mode wasn't explicitly requested.

---

## Output Format

```markdown
## Conductor Slice Drafted

I have scaffolded the slice: `{slice_filename}`

**Objective:** {summary}
**Phase:** {phase_name}
**Hard Constraint:** {constraint_summary}

Please review the drafted slice. Let me know if you approve or if we need to adjust the scope before implementation.
```

---

## Escalation

> "Halt. The request spans multiple architectural layers. Should we upgrade this to a `full` Conductor plan or split it into multiple smaller slices?"
