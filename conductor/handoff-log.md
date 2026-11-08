# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/s3-identifiers (shared identifier resolution, spec S3)

Commit: 7c96545
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S3 (D4; findings U4, U5, U7) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§1, U4/U5/U7, D4, S3), mcp/{tools,server}.py, cli/query.py, validation.py, errors.py.
Exact Next Steps: twin gate, operator merges. S9 and S11 build on `identifiers.py`. Parallel lanes (S5, S7, #68): merge `origin/main`, hand-resolve handoff/CHANGELOG, regenerate `docs/reference.md`.

### What changed

- New `strata_lookml/identifiers.py`, the one resolver for `mcp/tools.py` and `cli/query.py`: `resolve_table` (exact or unique dot-boundary suffix; ambiguous -> `InvalidInput` listing candidates), `resolve_explore` (`model` optional, `model.explore` accepted), `resolve_field` (`view.field`), `parse_changed` (`kind:name`, `{kind,name}`, `.lkml` paths, bare name = view).
- `strata_impact` echoes the resolved `physical_table` plus `resolved_from` (the input when it differed, else null). `strata_explore_deps` echoes `model` and `explore`; `model` is optional on the tool and the CLI (`strata query explore EXPLORE [MODEL]`). `strata_query_field`/`strata query field` take `view.field` as one argument. Unknown model -> `NotFound` (explore_deps and view_sources).
- `validation.ChangedObject.from_value` delegates to `parse_changed`; the CLI's `_file_to_changed` is deleted and `strata query scope` passes its args straight through.
- Tool descriptions and CLI help updated; `docs/reference.md` regenerated.

### Deviations from the spec

- A bare name in `changed` is now a view (spec: "bare = view"), so the old `invalid_input` for `"bogus"` is gone; `tests/test_error_contract.py` now uses `"view:"` as the malformed example.
- `strata_explore_deps` ambiguity cannot arise from LookML today: the resolver keys explores by name across models, so two models sharing an explore name collapse to one node. The ambiguity path is implemented and tested against a hand-built graph; the collapse is a separate pre-existing limitation, not fixed here.

### Gates

pytest 300 passed (+23 in `tests/test_identifiers.py`), ruff check + format --check clean, mypy clean. Negative control: `tests/test_identifiers.py` against a detached worktree of origin/main fails 18 of 23 (the 5 passes are the unchanged positional forms and unknown-object errors).
