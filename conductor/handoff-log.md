# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/s4-check-gate (`strata check` is a real CI gate, spec S4)

Commit: d86b7ac
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S4 (D1 minus baseline; finding B1) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§1, B1, D1, S4), cli/check.py, cli/_contract.py, errors.py, pipeline.py, l1/enrich.py, l1/schema.py, l1/types.py, ir/resolver.py, synthesis/verdicts.py, strata-ci.yml, strata-weekly.yml, README CI sections, docs check examples.
Exact Next Steps: twin gate on the PR, operator merges. Then S5 (`check --baseline` / `--write-baseline`): filter `gate.evaluate_gate`'s `failures` by `id` — every finding already carries a stable id (`dead:…`, `pdt:<view>`, `schema:…`, `resolution:<kind>:<type>:<subject>`, explore node id for verdict violations).

### What changed

- `strata_lookml/gate.py` (new API module): `evaluate_gate(graph, fail_on) -> {passed, failures, counts}` is the one gate decision; `cli/check.py` (argument parsing + output only, per `cli/AGENTS.md`) and `tests/test_scenarios.py` both call it. Codex P1 round 1 moved it out of the CLI layer. Integrity (resolution errors, verdict-evidence violations) always fails; missing repo / no `.lkml` already raise `StrataError` in `pipeline._repo_graph` (S1) and reach exit 1 through `StrataGroup`, with the `{error, code, hint}` envelope on stdout under `--json` (`JsonCommand`), so there is no second exit path. `--fail-on` (default `none`) adds `dead-code`, `unused-pdt`, `zombie-pdt`, `drift`, or `all`. Unknown category → `BadParameter` (exit 2); a category without its fixture → `UsageError` (exit 2), since it would otherwise pass by construction. `counts` has every category, `null` when its fixture was not loaded; failures sorted, JSON `sort_keys`.
- `tests/test_scenarios.py`: the old in-command assertions, parametrized over fixtures / gcs_analytics / thelook / enterprise_mono, each with the categories it must produce.
- CI: `strata-ci.yml` check steps renamed "(integrity gate)"; pytest now carries the scenarios. `strata-weekly.yml`: dropped the `gate: true` special case, `strata check` runs on every playground, plus `pytest tests/test_scenarios.py -k <name>`; checkout now uses `submodules: recursive`.
- Docs: README CI Gate + demo output + CI pipeline section, cli-guide, runbook, testing, CONTRIBUTING, the `strata_workflow` skill; `docs/reference.md` regenerated.

### Found on the way

- The weekly workflow checked out without submodules, so gcs_analytics and thelook were empty dirs there. That is the likely cause of the old comment's "sparse playgrounds don't reliably produce every signal" / "Py3.11 L1 emptiness bug"; locally on 3.14 both produce all their signals. Since S1 an empty dir fails with `no .lkml files`, so the weekly gcs/thelook jobs would have failed at `strata outputs` anyway. Fixed here with `submodules: recursive`; not verified on a 3.11 runner (the PR's CI runs 3.11 with submodules).

### Deviation from the spec

- None in behaviour. `--fail-on X` without X's fixture is a usage error; the spec does not say, and a silent pass was the alternative.

### Gates

pytest 241 passed (231 before; +6 in `tests/test_cli.py`, +4 in `tests/test_scenarios.py`), ruff check + format --check clean, mypy clean, `gen_reference.py --check` clean, dashboard JS check pass, the three CI `strata check` steps pass, `strata validate` 10 passed / 1 warning (handoff hash not reachable before this commit). Against the origin/main check.py all 6 CLI tests fail. Mutations, each failing its own test: resolution-error loop removed, fixture requirement removed, `fail_on` ignored (drift ids + JSON), default `all` (thelook default), lkml check removed in pipeline (empty dir), drift findings dropped (all 4 scenarios).
