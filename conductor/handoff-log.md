# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — fix/n9-model-scoped-explores (explores keyed by model, finding N9)

Commit: 4ad8164
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: patch — finding N9 of `ux-agentic-cli-docs-spec-2026-11-08.md` (context: D4, D13).
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§2 N9, D4, D13), ir/{parser,builder,resolver,types,store,source_lines}.py, identifiers.py, navigate.py, validation.py, mcp/tools.py, l1/{enrich,types}.py, synthesis/slices.py, outputs/{dashboard,pr_report,artifacts}.py, pipeline.py, tests/test_identifiers.py.
Exact Next Steps: twin gate, operator merges. If S8 lands first, merge `origin/main`, hand-resolve handoff/CHANGELOG, re-run `python scripts/gen_reference.py`.

### What changed

- Root cause was the resolver, not the ids: explore node ids were already `explore:<model>:<name>`, but `_collect_declarations` keyed explore definitions by name across all models, so a second model's same-named explore became a refinement of the first (one node, the second model's base view/joins, the first model's view orphaned).
- `ir/resolver._resolve_explores`: per-model namespaces. Layers, later wins: the one other model defining a name (cross-model `extends` base — thelook and enterprise_mono rely on it) < explores declared outside model files (shared, one model-less node as before) < the model's own. A model-file refinement of a name the model does not define goes to the shared explore if one exists; it never reaches another model's node. Errors de-duplicated across namespaces. Explores emitted by (name, model).
- One derivation: `ir.types.explore_id(model, name)` (`explore:<model>:<name>`) and `explore_key(model, name)` (`<model>.<name>`, the L1 fact key). Consumers routed: resolver, identifiers, navigate, validation, mcp/tools (`strata_explore_deps`, impact), synthesis/slices, l1/enrich (dead code, view consumers, evidence facts), l1/types (`ExploreUsage.key`, `ContentReference.explore_key`), outputs/dashboard (usage map, dead lookup, query count), outputs/pr_report. Not routed: the dashboard JS `exploreNodeIdFromKey` (JS-side mirror of the same rule; unchanged format) and `navigate._match_explores`, which parses ids.
- `ir/store.IR_FORMAT = 2`, recorded in `describe_inputs`; a cache written before it has no `ir_format`, so its inputs never match and it is rebuilt.
- Dashboard: an explore's graph label is `model.explore` when another model has an explore of that name; otherwise the bare name (unchanged for every existing fixture).
- Fixture `tests/lookml/twin_models` (in-tree, not a submodule): `retail.orders` over `retail_orders`, `wholesale.orders` over `wholesale_orders` + a wholesale-only refinement joining `accounts`.

### Deviations from the brief

- Id scheme kept as `explore:<model>:<name>` rather than the suggested `explore:<model>.<explore>`: the existing ids were already model-scoped, every artifact/evidence id and dashboard anchor uses them, and `:` stays unambiguous where `.` is not (identifiers.py already handles explore names containing a dot). No id format changes; the only visible change is the label of a shared-name explore.
- Cross-model `extends` fallback kept (not real Looker semantics, but enterprise_mono's fixture uses it across 6+ models and `strata check` fails without it).

### Gates

pytest 369 passed (365 before; +5 in `tests/test_model_scoped_explores.py`, -1: the hand-built ambiguity test in test_identifiers.py is replaced by the real-LookML one), ruff check + format --check clean, mypy clean (CI invocation), dashboard JS syntax OK, `docs/reference.md` regenerated with no diff. Negative controls: the new tests against origin/main code (detached worktree, PYTHONPATH to its src) fail 5 of 5 (merged node with `wholesale_orders`; dead set `{view retail_orders}`; DID NOT RAISE InvalidInput; `only_b` leaked into model a; KeyError on the missing node). Mutations: dropping `ir_format` from `describe_inputs` fails the cache test (serves the merged graph); dropping the cross-model layer fails 4 existing tests (thelook/enterprise check + scenarios). `strata outputs` for gcs_analytics, thelook, enterprise_mono (the CI fixtures) is identical to origin/main's apart from timestamps (every artifact, dashboard HTML included); emitting by (name, model) is what keeps enterprise_mono's register order — per-model emission had reordered it.
