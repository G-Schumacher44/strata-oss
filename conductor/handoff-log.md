# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/wb-s4b-triage-core (triage core and link builder, workbench S4b)

Commit: 8dba45c
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S4b of `workbench-spec-2026-11-08.md` (D2, D3, D4; mockup items M6, M8).
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D2-D4, S4b, §6b) and validation report (M6, M8), gate.py, config.py, safe_paths.py, errors.py, ir/store.py, ir/types.py, identifiers.py, l1/enrich.py, cli/check.py.
Exact Next Steps: twin gate, operator merges. Then S4 (router + server) consumes `triage_rows` and `links`; S4c (`strata findings --format lines` + `strata ack`/`unack`) and S11 (links out) can follow S4b directly.

### What changed

- `triage.py`: `TriageStore.open(repo, graph)` at `config.triage_path(repo)` = `~/.strata/triage/<repo_key>.json` (dir via `ensure_private_dir`, file 0600, write via `check_write_destination` + temp + `os.replace`). Document `{version, rev, ids: {id: {category, acked_at, note?, unacked_at?, first_absent_at?}}}`. `.acknowledge(ids, note=None)`, `.unacknowledge(ids)`, `.snapshot()`, `.observe()`.
- Append-only (M8): unack sets `unacked_at`; re-ack clears it. `observe()` stamps `first_absent_at` the first time a stored id is absent from a category whose check ran, clears it when the id reappears, and prunes the entry once absent for 90 days (`ABSENT_TTL`). A category that did not run is never stamped.
- Concurrency: re-read, apply per id, write `rev+1`, replace only if the on-disk `rev` is still the one read (`_current_rev`, checked just before `os.replace`); 3 tries then `StrataError("triage state changed concurrently", hint="retry")`. No fcntl (D4), so a write landing between that check and the replace can still be lost; the window is one stat-and-read.
- Allowlist: `acknowledge` accepts an id only if a current finding carries it or the store already holds it; `unacknowledge` only stored ids. Any miss -> `InvalidInput`, nothing written. Notes cap at 2000 chars.
- `triage_rows(graph, baseline, store)`: frozen `TriageRow`s, status derived once (D4): baselined (wins over acknowledged, ack record kept, M6) / acknowledged / new for current ids; then acked or baselined ids absent now: fixed when their category ran, not_checked when it did not. Integrity counts as always checked.
- `links.py`: `object_path` (explore/view/pdt/table/field; None for kinds with no page), `finding_path` (`quote(id, safe="")`), `link(base, path)` (no base -> None; `.html` or `#` base -> `<base>#/<path>` replacing any old fragment; else `<base>/<path>`).
- Import-graph guard (`tests/test_triage.py`): AST walk of strata_lookml's own import closure from triage, links, gate and mcp/tools (function-level imports too) bans `http`, `textual`, `jinja2`, `strata_lookml.workbench`, `strata_lookml.tui`; a second assertion keeps `strata_lookml.triage` out of the gate's closure.

### Deviations from the brief

- `TriageStore.open(repo, graph)`, not `open(repo)`: the allowlist (D4: "enforced in the store") needs the current finding ids, and `observe()` needs which categories ran. `triage_rows` refuses (ValueError) a store opened on a different graph.
- Each entry also stores its `category` (taken from the current finding at ack time): "fixed" vs "not checked" for an absent acked id depends on whether its category ran, which the id alone does not say.
- `first_absent_at` is stamped on every stored entry, unacked ones included, so the 90-day TTL also prunes unacked records (otherwise they would never leave the append-only store).
- `triage_rows` calls `store.observe()`, so reading rows can write the store (only when an absence stamp or prune changed something). No file is created when nothing is stored.
- One row per id: a duplicated id (G14) is one row with its first record's label, subject and line; `/finding/<id>` (S6) shows all records.
- HOME is redirected per test module (`_home` fixture in `tests/test_triage.py`), not globally in conftest, so other suites' HOME handling is unchanged.

### Gates

pytest 471 passed, 1 skipped (before: 424 passed, 1 skipped); ruff check + format --check clean on src/ tests/ scripts/; mypy `src/strata_lookml --ignore-missing-imports` clean; `check_dashboard_js_syntax.py` and `gen_reference.py --check` pass (no CLI/MCP surface change). Fail-before: `tests/test_triage.py` against origin/main (detached worktree) errors at collection (no `strata_lookml.triage`). Negative controls, each mutation in a throwaway detached worktree failing at least one test: ack-wins-over-baseline, not_checked->fixed, rev check removed (2 fail), allowlist removed, TTL prune removed, re-ack keeps `unacked_at`, symlink read refusal removed, file mode 0644, hash-form link for `#` bases; the import guard fails on each of six planted imports (http, from-http, textual, jinja2, workbench, tui) placed one module down inside a function.
