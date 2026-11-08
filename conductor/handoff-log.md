# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/wb-s1-finding-records (finding record seam, workbench S1)

Commit: 5676289
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S1 of `workbench-spec-2026-11-08.md` (G4, G8, G14, D2; mockup items M1, M3).
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the workbench spec and validation report, gate.py, ir/source_lines.py, l1/{enrich,schema,types}.py, ir/resolver.py, tests/test_cli.py.
Exact Next Steps: twin gate, operator merges. S2 and S3 land serially; on a main move, merge `origin/main`, hand-resolve, regenerate the reference, re-run the gates.

### What changed

- `gate.finding_records(graph)`: one record per opt-in finding, `{category, id, message, label, subject_id, source_file, source_line, evidence_ids, cost_usd?}`. `findings_by_category` is now a projection (`{category, id, message}` rows, None where facts were not loaded) and `baseline_document` still projects ids from that, so there is one source of findings.
- Subjects: dead view -> `view:<name>`, dead explore -> its explore node, PDT -> `pdt:<view>`, missing_column -> the field node, missing_table -> `physical_table:<name>`. `cost_usd` only on PDT records.
- Labels (M3): dead-code and PDT drop the prefix; missing_column `<view.field> <- <table>.<col>` (project and dataset dropped); missing_table `<dataset>.<table>`. Full id stays the key.
- M1: `attach_source_lines` gives `pdt:<name>` the line of `view:<name>`.
- Integrity: `finding_records` leads with integrity records (label `subject: reason`); `findings_by_category` covers the opt-in categories only.
- G14: duplicate ids yield multiple records, ids unchanged; the baseline de-duplicates.

### Deviations from the brief

- (Closed in review.) Integrity failures are records too (category `integrity`, the gate's ids); `_integrity_failures` projects from them. Resolution errors carry no node, file or line, so `subject_id`/`source_file`/`source_line` are None there; explore failures cite their explore node.
- `physical_table` nodes have no line, so a missing_table record cites the line of the first view that reads the table (via `view->physical_table`).
- G14 is not reachable from LookML: field ids are `view.field`, and a dotted-name pair collapses to one field node. The collision test injects a duplicate drift record into the L1 facts.

### Gates

pytest 390 passed, ruff check + format --check clean, mypy `src/strata_lookml` clean. Golden: `strata check --fail-on all --json` and `--write-baseline` outputs byte-identical to origin/main for enterprise_mono, gcs_analytics and thelook (fixtures). Negative control: `tests/test_finding_records.py` on origin/main code (detached worktree) fails to import `finding_records`, and its PDT nodes have `source_line` None on all 5.
