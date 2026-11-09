# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/wb-s2-strata-object (workbench S2: `strata_object`)

Commit: 73dbfcc
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S2 of `workbench-spec-2026-11-08.md` (D2, G3/G6, M5; operator Q5: yes, an MCP tool).
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, workbench spec + validation (M5), mcp/{tools,server}.py, cli/query.py, identifiers.py, l1/{enrich,types,schema}.py, gate.py.
Exact Next Steps: twin gate, operator merges. S1 (`finding_records`) and S3 land in parallel; once S1 merges, `_node_finding_ids` in `mcp/tools.py` should read `finding_records(...).subject_id` instead of matching per category.

### What changed

- `mcp/tools.strata_object(graph, kind, name)` for explore | view | pdt | table | field: `{kind, id, name, source_file, source_line, upstream, downstream, findings, coverage, content, details}`. Names resolve through `identifiers.py` (`model.explore`, `view.field`, table suffix); ambiguous -> InvalidInput with candidates, unknown -> NotFound.
- Reuse, not re-derivation: explore lineage from `strata_explore_deps`, table downstream from `strata_impact`, view/field downstream from `view_consumer_map`, PDT downstream from `direct_view_consumers`; findings are the ids of `gate.findings_by_category` records on the node (dead-code, PDT, drift).
- M5: explores carry `content` = `{reference_count, by_type, items, window, window_label}` from the existing L1 `content_references` / `evidence_facts` counts. The window is the usage period the facts were pulled for (`l1.period`, 30d in the fixtures), labelled "viewed in <days>d", not 90d and not all-time. `content` is null (never 0) when usage was not checked, and for non-explore kinds. Content items also appear as the explore's downstream.
- MCP tool `strata_object` (read-only, every parameter described) and CLI `strata query object KIND NAME` (JsonCommand). README tool counts (19 / 18 read-only) and table, `docs/reference.md` regenerated.
- `gate` is imported lazily inside `_node_finding_ids` (gate -> synthesis.slices -> mcp.tools would otherwise cycle).

### Deviations from the brief

- Window label is "viewed in 30d" (the data's real window), not the spec's "90d" — the fixtures and the Looker provider default to 30 days; the label is read from `l1.period`.
- PDT `source_line` is null until S1 (M1). Added a `details` key (kind-specific facts: explore joins/field count, field definition, PDT ledger record, view field count) beyond the brief's list.

### Gates

- [x] pytest 397 passed; ruff check; ruff format --check; mypy src/strata_lookml --ignore-missing-imports; docs/reference.md regenerated.
- [x] Fail-before: `tests/test_strata_object.py` against a detached worktree of origin/main errors at collection (no `strata_object`).
