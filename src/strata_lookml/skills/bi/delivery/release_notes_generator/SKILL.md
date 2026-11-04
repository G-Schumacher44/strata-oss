# Skill: release_notes_generator

domain: bi/delivery
mode: draft
complexity: low
version: 0.1.0

> Turn a git diff or list of changed LookML files into stakeholder-ready
> release notes. Translates technical changes into business impact language.
> One pass: no LLM judgment needed for most changes.

---

## Trigger

- Merging a LookML PR to production
- End-of-sprint BI release summary
- Stakeholder asks "what changed in Looker this week?"
- Output of `strata_validation_scope` after a merge

---

## Inputs

| Input | Required | Source | Description |
|---|---|---|---|
| `changed_files` | yes | git / human | List of changed `.lkml` file paths |
| `pr_title` | no | human / git | PR title for context |
| `audience` | no | human | `stakeholder` (default) or `technical` |

---

## Allowed Tools

- `strata_mcp.strata_validation_scope` — get impacted views, explores, and fields from changed files
- `strata_mcp.strata_dead_code_register` — flag if a changed explore is dead (should not appear in notes)
- file read: changed `.lkml` files for field label and description extraction

---

## Forbidden

- Do not invent business context — only use what is in the LookML labels, descriptions, and PR title
- Do not include internal field names in `stakeholder` audience output — use `label:` values only
- Do not include dead explores in stakeholder-facing notes

---

## Procedure

1. `strata_validation_scope(changed_files)` → get impacted views, explores, fields
2. For each changed file: read LookML to extract added/modified/removed fields with their `label:` and `description:`
3. Filter out any explores in the dead code register
4. Classify each change:
   - New field → **Added**
   - Changed `sql:` or `type:` → **Updated** (may affect existing queries)
   - Removed field → **Removed** (breaking — flag separately)
   - New explore → **New data available**
   - Removed explore → **Retired** (flag separately)
5. For `stakeholder` audience: use `label:` values, omit technical detail, group by explore
6. For `technical` audience: include field names, SQL changes, join modifications
7. `[JUDGMENT]` If a removed field is used in saved Looks or dashboards → flag as **BREAKING CHANGE**
8. Lead with breaking changes, then additions, then updates
9. Output release notes — do not post anywhere without human approval

---

## Stop Conditions

- `changed_files` is empty → halt, nothing to document
- All changes are to dead explores only → note this, produce internal-only summary

---

## Output Format (stakeholder)

```markdown
## BI Release Notes — {date}
{pr_title if provided}

### New This Release
- **{Explore Label}** — {field label}: {description or one-sentence summary}

### Updates
- **{Explore Label} / {Field Label}** — calculation updated. Existing reports using this field will reflect the new logic.

### Retired
- **{Explore Label}** — this data source has been retired. Contact the BI team for alternatives.

### Breaking Changes ⚠️
- **{Field Label}** removed from **{Explore Label}**. Saved reports using this field will error until updated.
```

---

## Output Format (technical)

```markdown
## BI Release — Technical Summary — {date}

### Changed Files
- `{file}`: {views affected}, {explores affected}

### Field Changes
| File | Field | Change | Impact |
|---|---|---|---|
| `{file}` | `{view}.{field}` | sql updated | {explores using it} |

### Breaking Changes
- `{view}.{field}` removed — referenced in {n} saved Looks
```

---

## Escalation

> "Warning: `{field}` was removed but appears in saved Looks or dashboards.
> This is a breaking change. Confirm removal is intentional before merging."

---

## Examples

- `examples/good_input.md`
- `examples/good_output.md`
