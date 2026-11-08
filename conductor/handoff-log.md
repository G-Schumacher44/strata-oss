# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/s5-check-baseline (`strata check --baseline`, spec S5)

Commit: 4d71071
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S5 (D1 rest) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: small
Context Loaded: AGENTS.md, the spec (D1, S4, S5), gate.py, cli/check.py, tests/test_cli.py, README CI Gate.
Exact Next Steps: twin gate, operator merges. Merge `origin/main` when S3/S7/#68 land (hand-resolve handoff/CHANGELOG, `python scripts/gen_reference.py`).

### What changed

- `gate.py` owns the baseline: `write_baseline`/`baseline_document`, `load_baseline` (`BaselineError`), `findings_by_category` (was private), and `evaluate_gate(..., baseline=)` which subtracts known ids from the `--fail-on` categories before failing. `cli/check.py` only parses flags and formats.
- File format: JSON `{"version": 1, "findings": {category: [sorted unique ids]}}`, trailing newline; only categories whose facts were loaded are written.
- With `--baseline` the result adds `baselined` and `stale_baseline_ids` (stale = baselined id absent from a loaded category; a category not loaded this run is not judged). Without it the `--json` shape is unchanged.
- README CI Gate section (legacy-repo adoption), CHANGELOG Added, regenerated `docs/reference.md`.

### Deviations from the spec

- Ids are stored per category, not one flat list, so stale detection cannot misfire on a category whose fixture is not loaded in the checking run.
- `--write-baseline` also runs the gate afterwards (integrity failure still exits 1); it is mutually exclusive with `--baseline`.
- Unreadable/invalid baseline exits 2 via `click.UsageError` (a `StrataError` would exit 1 per the CLI contract).

### Gates

pytest 285 passed (+8 in `tests/test_cli.py`), ruff check + format --check clean, mypy clean (CI invocation), `gen_reference.py --check` clean. Negative controls: the new tests run against a detached `origin/main` worktree fail 8 of 8 (the bad-baseline cases assert our message names the file, so click's "no such option" cannot satisfy them).

Review round (Codex P1): `--write-baseline` could truncate a source file. `write_baseline` now resolves the destination and refuses (usage error, exit 2, before any write) a symlink final component, a `.lkml`/`.lookml` target, a directory, or an existing file that is not a prior Strata baseline; the write is temp-file-in-same-dir + `os.replace`. +4 tests (pytest 289); against the pre-fix code 3 of 4 fail (overwrite-a-previous-baseline is a guard that passes on both).
