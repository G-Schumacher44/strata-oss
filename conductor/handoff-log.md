# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/s7-cache-location (IR cache location + identity, spec S7)

Commit: ce24f62
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <n> --json mergeCommit`.
Conductor Mode: feature — spec S7 (D7; findings N1, N2; addendum from #70) of `ux-agentic-cli-docs-spec-2026-11-08.md`.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, the spec (§2 N1/N2, D7, S7 + addendum), config.py, ir/store.py, pipeline.py, mcp/server.py, cli/{build_ir,mcp,main}.py, l1/looker.py (token dir helpers), security/deployment docs.
Exact Next Steps: twin gate, operator merges. S8 (`mcp validate` readiness) builds on `config.load_cache_path` and `ir.store.cache_age_seconds`/`cache_inputs`; it rewrites the cache line of `mcp validate` (S7 only routed it through the resolver). If S3/S5/#68 land first, merge `origin/main`, hand-resolve handoff/CHANGELOG, re-run `python scripts/gen_reference.py`.

### What changed

- `config.py`: `default_cache_path(repo)` = `~/.strata/cache/<repo-name>-<sha256(abs path)[:12]>.db`; `load_cache_path(repo, cache=None)` = `--cache` → `STRATA_CACHE_PATH` → default, the one resolver; `ensure_private_dir(dir, tighten=)` (missing levels created 0700; `tighten` chmods an existing Strata-owned dir). `l1/looker.prepare_token_dir` now creates through `ensure_private_dir` (refusal rule unchanged).
- `ir/store.py`: the cache row stores `inputs` (repo path + `lookml_fingerprint` — count, max `mtime_ns`, total size, hash of relative paths over `ir/parser.lkml_paths` — and fixture paths + `mtime_ns`, from `describe_inputs`); `save_ir` writes a 0600 temp file beside the target and `os.replace`s it (readers see the old or new cache, never half; an interrupted write leaves the old one), dir 0700 (tightens `~/.strata/cache`); readers (`cache_age_seconds`, `cache_inputs` via `_read_cache_column`) treat a missing table/column or a non-SQLite file as a miss, and `load_or_build` treats a failed `load_ir` after the freshness check as a miss; `cache_inputs`, `cache_is_fresh(path, inputs, max_age)`.
- `pipeline.py`: `build_and_cache` (inputs captured before the build) and `load_or_build` (reuse only when inputs match and age < max). The server's `load_configured_graph` and `strata build` go through them; the four path decisions (server `_cache_path`, build, `mcp validate`, `mcp config`) are gone.
- `strata build --cache` declares `STRATA_CACHE_PATH`. `strata clean` removes the repo's `~/.strata/cache` entry plus legacy `strata_ir.db` under the repo; `--repo` declares `STRATA_REPO_PATH` (addendum).
- Docs: security-hardening write table, enterprise-deployment, SECURITY.md, README (commands table + MCP layer note), cli-guide; regenerated `docs/reference.md`; CHANGELOG Changed with the compat note.

### Deviations from the spec

- `strata clean` deletes the default-location entry, not a cache at `STRATA_CACHE_PATH`/`--cache` (a user-chosen path is not Strata's to delete). Without `--repo`/env it cleans the cwd's entry.
- The N1 test asserts `usage_checked` (S2's field) rather than the spec's older `has_l1` wording.
- `ensure_private_dir` creates every missing level 0700, so a custom `--token-path` with missing parents now gets 0700 parents too (narrower than before).

### Gates

pytest 340 passed (277 before S7; +11 in `tests/test_cache_location.py`, +23 from merging S3 #73, +12 from S5 #72, +16 from S10 #68, +1 from S11 #75; 340 total), ruff check + format --check clean, mypy clean (CI invocation). Negative controls: the new tests against `origin/main` code (detached worktree) fail 6 of 7 — the server test fails `usage_checked False is True`; the passing one is the same-name-repos invariant of the new resolver. Mutations: `cache_is_fresh` ignoring inputs fails the N1 test; dropping the `.lkml` fingerprint from the inputs fails the lkml-edit test (`13 == 13 + 1`); dropping the 0600 create/chmod fails the mode test. Real `~/.strata` untouched by the suite (no `cache/` dir).

Review (head): the repo was keyed by path only, so a `.lkml` edit inside the reuse window served a stale IR. Inputs now carry a stat-only `.lkml` fingerprint over the parser's own discovery; `test_server_rebuilds_after_a_lkml_edit_within_the_reuse_window`.
Review (Codex P2, store.py): the drop/create/insert ran with DDL in autocommit, so a concurrent server start saw no `ir_cache` table and `cache_age_seconds` raised; a crash between the steps left a cache that never self-healed. Now temp file + `os.replace`, and damaged caches are a miss. Tests: `test_interrupted_cache_write_leaves_the_previous_cache_whole`, `test_server_rebuilds_a_damaged_cache_instead_of_failing[drop_table|not_a_database]` — all 3 fail on the previous head d40b07b (`assert None is not None`, `no such table: ir_cache`, `file is not a database`). `test_load_ir_open_cannot_create_…` now expects `cache_age_seconds` → None (miss) instead of a raise; its no-ghost-file invariant is unchanged.
