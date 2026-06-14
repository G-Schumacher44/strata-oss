# Slice NN: [Title]

Date: YYYY-MM-DD
Status: queued | active | review | stable
Phase: [phase number]
Depends: [prior slice or "none"]

```yaml
conductor_mode: slice
context_budget: low | medium | high
handoff_required: true
stable_tag_required: false
```

## Objective

One paragraph. What problem does this slice solve? Why now?

## Scope

Which layer(s) does this touch? (L0 IR / MCP / L1 / L2 / Governance / Vendor)

## Implementation Order

Numbered steps. Most constrained first.

1.
2.
3.

## The Hard Constraint (if any)

Call out the make-or-break correctness requirement explicitly. What must be true
before anything downstream is trusted?

## Acceptance Criteria

- [ ] Gate 1
- [ ] Gate 2
- [ ] `strata validate` — spine passes
- [ ] `.venv/bin/pytest` — all tests pass
- [ ] `conductor/handoff-log.md` — STABLE entry with Commit: hash
