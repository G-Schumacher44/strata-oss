# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/wb-s4b-triage-core (triage core and link builder, workbench S4b)

Commit: 3dc79ff
  (Latest implementation commit, review round 3; earlier 8dba45c, f6d0d50, 629002d. The PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — slice S4b of `workbench-spec-2026-11-08.md` (D2, D3, D4; mockup items M6, M8).
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, the workbench spec (D2-D4, S4b, §6b) and validation report (M6, M8), gate.py, config.py, safe_paths.py, errors.py, ir/store.py, ir/types.py, identifiers.py, l1/enrich.py, cli/check.py.
Exact Next Steps: twin gate, operator merges. Then S4 (router + server) consumes `triage_rows` and `links`; S4c (`strata findings --format lines` + `strata ack`/`unack`) and S11 (links out) can follow S4b directly.

### What changed

- `triage.py`: `TriageStore.open(repo, graph)` at `config.triage_path(repo)` = `~/.strata/triage/<repo_key>.json` (dir via `ensure_private_dir`, file 0600, write via `check_write_destination` + temp + `os.replace`). Document `{version, rev, ids: {id: {category, acked_at, note?, unacked_at?, first_absent_at?}}}`. `.acknowledge(ids, note=None)`, `.unacknowledge(ids)`, `.snapshot()`, `.observe()`.
- Append-only (M8): unack sets `unacked_at`; re-ack clears it. `observe()` stamps `first_absent_at` the first time a stored id is absent from a category whose check ran, clears it when the id reappears, and prunes the entry once absent for 90 days (`ABSENT_TTL`). A category that did not run is never stamped.
- Concurrency: writers are serialized by an OS advisory lock on a dedicated `<store>.lock` (`fcntl.flock` on POSIX, `msvcrt.locking` on Windows; 0600, write-guarded by `check_write_destination`, opened `O_NOFOLLOW`, never deleted, never written), held around the rev check and `os.replace`. The kernel releases it when the holder dies, so there is no stale-lock handling. The rev check stays as defence in depth: re-read, apply per id, write `rev+1`, replace only if the on-disk `rev` is still the one read; 3 tries (50/100 ms backoff) then `StrataError("triage state changed concurrently", hint="retry")`. On Windows `msvcrt` gives up after ~10 s -> `StrataError("triage store is locked by another writer", hint="retry")`.
- Allowlist: `acknowledge` accepts an id only if a current finding carries it or the store already holds it; `unacknowledge` only stored ids. Any miss -> `InvalidInput`, nothing written. Notes cap at 2000 chars.
- `triage_rows(graph, baseline, store)`: frozen `TriageRow`s, status derived once (D4): baselined (wins over acknowledged, ack record kept, M6) / acknowledged / new for current ids; then acked or baselined ids absent now: fixed when their category ran, not_checked when it did not. Checked categories come from each category's own facts (`FINDING_CATEGORIES` over `analysis_coverage`): usage for dead-code / unused-pdt / zombie-pdt, schema for drift; G16's `content` flag feeds dead code but gates nothing. Integrity counts as always checked.
- `links.py`: `object_path` (explore/view/pdt/table/field; None for kinds with no page), `finding_path` (`quote(id, safe="")`), `link(base, path)` (no base -> None; `.html` or `#` base -> `<base>#/<path>` replacing any old fragment; else `<base>/<path>`).
- Import-graph guard (`tests/test_triage.py`): AST walk of strata_lookml's own import closure from triage, links, gate and mcp/tools (function-level imports too) bans `http`, `textual`, `jinja2`, `strata_lookml.workbench`, `strata_lookml.tui`; a second assertion keeps `strata_lookml.triage` out of the gate's closure.

### Deviations from the brief

- `TriageStore.open(repo, graph)`, not `open(repo)`: the allowlist (D4: "enforced in the store") needs the current finding ids, and `observe()` needs which categories ran. `triage_rows` refuses (ValueError) a store opened on a different graph.
- Each entry also stores its `category` (taken from the current finding at ack time): "fixed" vs "not checked" for an absent acked id depends on whether its category ran, which the id alone does not say.
- `first_absent_at` is stamped on every stored entry, unacked ones included, so the 90-day TTL also prunes unacked records (otherwise they would never leave the append-only store).
- `triage_rows` calls `store.observe()`, so reading rows can write the store (only when an absence stamp or prune changed something). No file is created when nothing is stored.
- One row per id: a duplicated id (G14) is one row with its first record's label, subject and line; `/finding/<id>` (S6) shows all records.
- HOME is redirected per test module (`_home` fixture in `tests/test_triage.py`), not globally in conftest, so other suites' HOME handling is unchanged.

### Review round 1 (PR #85)

- Codex P2 (rev check and replace not mutually exclusive: two writers that both read rev 0 could both succeed, the last silently dropping the other's ids): fixed with the O_EXCL lock above. New test races a second writer between the first's check and its replace; it now raises instead of landing and being overwritten. Stale-lock and fresh-lock behaviour tested.
- Artemis should_fix (note validation untested): `test_acknowledge_refuses_a_bad_note` (non-string, over 2000 chars; exactly 2000 accepted).
- Apollo ACCEPT (note: could not re-run gates read-only).

### Review round 2 (PR #85 @ ae6b416)

- Codex P2 + Artemis should_fix (stale-lock recovery races: A stats a stale lock, B breaks it and takes a fresh one, A unlinks B's live lock): fixed by never breaking the lock. Conservative choice over an fcntl/msvcrt lock, which D4 rules out; the cost is a manual delete after a SIGKILL in a one-read-one-rename window.
- Artemis note (lock contention reported as "changed concurrently"): contention now raises its own "locked by another writer" error.
- Codex P2 (an old `first_absent_at` survived re-acknowledging a present id, so the TTL could prune a fresh ack a day later): `acknowledge` clears it when the graph shows the id present.
- Apollo ACCEPT_WITH_NOTES (could not re-run gates read-only).

### Review round 3 (head direction, superseding round 2's lock)

- Shape fix for the stale-lock race: the O_EXCL lock file and its no-break / staleness handling are gone; an OS advisory lock (above) replaces them. The spec's "no fcntl" (D4) assumed no Windows path; `msvcrt.locking` covers Windows.
- Tests: the cross-writer race test now runs the second writer in a thread blocked on the lock while the first sits between its check and its replace (both land, rev 2); a child process that takes the lock and is SIGKILLed never blocks the next writer (and a live holder really blocks a non-blocking probe); the lock file is never deleted and a symlink at its path is refused.
- Per-category coverage (head FYI after G16): a usage fixture without `content_references` still lets an absent dead-code id be fixed; drift without schema is not_checked.

### Gates

pytest 498 passed, 1 skipped after merging origin/main `7abc0ba` (S13 #84 on top of G16 #83; main alone 444 passed, 1 skipped; this slice adds 54); ruff check + format --check clean on src/ tests/ scripts/; mypy `src/strata_lookml --ignore-missing-imports` clean; `check_dashboard_js_syntax.py` and `gen_reference.py --check` pass (no CLI/MCP surface change). Fail-before: `tests/test_triage.py` against origin/main (detached worktree) errors at collection (no `strata_lookml.triage`). Negative controls, each mutation in a throwaway detached worktree failing at least one test: ack-wins-over-baseline, not_checked->fixed, rev check removed (2 fail), allowlist removed, TTL prune removed, re-ack keeps `unacked_at`, symlink read refusal removed, file mode 0644, hash-form link for `#` bases; the import guard fails on each of six planted imports (http, from-http, textual, jinja2, workbench, tui) placed one module down inside a function. Round 1 controls: lock never taken -> the race test fails (plus the three lock-seam tests); note validation removed -> both bad-note cases fail. Round 2 control: ack keeping the old absence stamp -> the retention test fails. Round 3 controls: the new tests against 629002d fail 6 (race, killed holder, dedicated lock, interrupted write, both interleave seams); `flock` not taken -> race + killed-holder tests fail; every category counted as run -> both not_checked tests fail.
