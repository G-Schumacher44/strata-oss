# Conductor Execution Modes

Status: active
Type: workflow-policy
Version: conductor-modes-v1

## Purpose

Define the smallest safe Conductor workflow for tasks. Conductor is
valuable when work changes architecture, layer boundaries, or cross-repo
coordination. It becomes too expensive when every small fix hydrates the
full history. These modes keep context spend proportional to risk.

## Core Rule

Start in the smallest mode that can safely complete the task. Escalate only
when the work crosses layer boundaries, the contract, runtime safety, or
cross-repo ownership boundaries.

---

## Mode Tags

Every active slice must declare:

```yaml
conductor_mode: patch | slice | full | audit
context_budget: low | medium | high
handoff_required: true | false
stable_tag_required: true | false
```

---

## Patch Mode

**Use for:** bug fix, one-file change, doc update, minor config tweak.

**Required reads:**
1. `AGENTS.md`
2. `conductor/CONDUCTOR_MODES.md`
3. `conductor/handoff-log.md` — latest block only
4. Target source / docs files

**Forbidden without written reason:**
- Full slice reads
- `conductor/archive/**` or `handoff-archive.md`
- Broad repo searches

**Expected output:**
- Small scoped diff
- Targeted validation
- Handoff entry only when the change is meaningful or changes the next safe action

---

## Slice Mode

**Use for:** planned implementation inside an existing slice spec.

**Required reads:**
1. `AGENTS.md`
2. `conductor/CONDUCTOR_MODES.md`
3. `conductor/index.md`
4. `conductor/README.md`
5. Active `conductor/slice-*.md`
6. `conductor/handoff-log.md` — latest block only
7. `git status --short --branch`

**Forbidden without written reason:**
- Reading every slice in `conductor/`
- `conductor/archive/**` or `handoff-archive.md`

**Expected output:**
- Slice-bounded implementation
- All Acceptance Criteria gates checked `[x]` before handoff
- `conductor/handoff-log.md` updated in the final commit
- Tests passing

---

## Full Conductor Mode

**Use for:** cross-layer change, new phase, architecture change, new external
dependency, cross-repo coordination, governance policy update.

**Required reads:**
1. Full authority order from `AGENTS.md`
2. `conductor/CONDUCTOR_MODES.md`
3. `conductor/index.md`
4. `conductor/README.md`
5. Active slice or new slice draft
6. `conductor/handoff-log.md` — latest block
7. Relevant docs files
8. Relevant code seams before implementation

**Expected output:**
- Updated governing docs before implementation
- Explicit layer ownership decisions recorded
- Handoff with mode, context loaded/skipped, and next safe action

---

## Audit Mode

**Use for:** review and assessment — code quality, correctness, coverage gaps.
No implementation.

Every audit must define:
- Audit objective
- Included surfaces
- Excluded surfaces
- Context budget
- Findings format
- Whether fixes are allowed or deferred to a new slice

**Expected output:**
- Findings before summary
- File references where possible
- Risk level per finding
- Explicit test gaps
- Compact handoff so future agents do not repeat the full audit

---

## Context Hygiene

- Do not read `conductor/archive/**` unless history is required.
- Do not read `handoff-archive.md` unless the active slice requires it.
- Read one active slice before reading every slice.
- Prefer targeted grep/find over broad repo searches.

---

## Handoff Mode Block

Every meaningful handoff must include:

```
Conductor Mode: slice
Context Budget: medium
Context Loaded: AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/index.md, active slice, handoff-log latest block.
Context Skipped: archive/**, handoff-archive.md.
Tag Posture: no stable tag required.
```

---

## Escalation Triggers

Escalate to Full Conductor Mode when:

- A change crosses layer boundaries
- A new external dependency is being introduced
- Cross-repo coordination is required
- Root governance docs (`AGENTS.md`) change
- The agent cannot explain which layer owns the decision

---

## Success Condition

This policy is working when agents enter the repo, choose the right mode,
avoid unnecessary context hydration, and still give high-risk work full review.
