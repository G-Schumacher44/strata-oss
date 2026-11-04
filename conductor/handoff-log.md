# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-03 — fix/batch-2026-11 (batch of ten correctness fixes)

Commit: 669e188 (last code commit on the PR branch, pre-merge anchor. This PR is meant to be
  REBASE-merged so the per-fix commits stay reviewable; rebase rewrites SHAs, so post-merge
  resolve the landed anchor with `git log --grep "one table-ref unquoting rule" origin/main`.)
Conductor Mode: patch — ten independent bug fixes batched into one PR, plus fixes for the
  unresolved Codex findings on their source PRs; no new slice.
Context Budget: medium
Context Loaded: AGENTS.md, conductor/AGENTS.md, conductor/CONDUCTOR_MODES.md, handoff-log latest
  block, source PRs #33 #35-#43 (diffs + unresolved review threads), src/strata/cli/{main,
  query,dashboard,outputs,conductor}.py, navigate.py, ir/{store,resolver,source_lines}.py,
  l1/{replay,looker}.py, viz/render.py, mcp/tools.py.
Context Skipped: handoff-archive.md beyond prepending the previous block; slices.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump — fixes only, no release trigger.
Exact Next Steps: review and rebase-merge the batch PR, then close #33 and #35-#43 as
  superseded; next, reconcile the two handoff-log readers (`strata conductor status` splits on
  "##" while strata_conductor_status only reads "## Date:" headers) — file an issue for it (the batch agent was not permitted to).

### What landed (one commit per source PR, handoff files dropped)

- #33 backtick-quoted BigQuery tables in PDT upstream SQL (Bug Hunt draft, reviewed fresh).
- #35 `<` escaped in chart HTML so data cannot close the script block.
- #36 navigate chart spec built as data (JSON), not an f-string YAML template.
- #37 `strata clean` sweeps `__pycache__` under `--repo`, not the cwd.
- #38 `dataset.table` anchors classify as physical tables when the IR has them.
- #39 `load_ir` raises FileNotFoundError instead of creating a ghost cache file.
- #40 ISO timestamps compared as instants; one shared `_latest_iso`.
- #41 source-line scan cache cleared on every build.
- #42 navigate chart written under the guarded output root (`~/.strata/output`).
- #43 DROPPED (see below).

### Review findings resolved (each its own commit with a test that fails without it)

- #36 `</script>` anchor in the chart: #35's escaping already neutralizes it once both land;
  pinned end-to-end by `test_navigate_chart_anchor_cannot_break_out_of_the_script_block`.
- #38 field/table collision: an exact `view.field` wins and the brief carries
  `ambiguous_anchor` (`test_navigate_two_part_anchor_prefers_exact_field_over_same_named_table`).
- #39 exists()/connect race: load_ir and cache_age_seconds open through one helper with
  `file:<abs>?mode=rw` (`test_load_ir_open_cannot_create_the_cache_even_if_exists_check_races`,
  `test_ir_cache_roundtrips_through_a_path_needing_uri_escaping`).
- #40 equal-instant ties: `_latest_iso` is a total order (parsed, instant, string)
  (`test_latest_iso_is_independent_of_row_order`).
- #33 own review: per-part backtick quoting and `${view}` refs
  (`test_sql_upstreams_backtick_per_part_quoting_and_view_refs`).
- #43 `clean --repo` deleting `<repo>/output`: Strata never writes there (dashboard defaults to
  `<cwd>/output/<repo>`, `strata outputs` requires `--out`), so the change is dropped and
  `test_clean_repo_never_deletes_output_inside_the_lookml_repo` fails if it returns.
- Local twin gate (Artemis P3s): per-part-quoted sql_table_name vs PDT upstream minted two
  nodes, and backtick-quoted CTEs became phantom tables — one `_unquote_table_ref` rule for
  both sides (`test_per_part_quoted_table_mints_one_node_for_view_and_pdt`,
  `test_sql_upstreams_backtick_quoted_cte_is_not_a_table`). Not fixed, pre-existing:
  load_configured_graph's cache_age_seconds→load_ir window (not a regression) and
  navigate chart filename collisions/length for sanitized anchors.
- Handoff-location P1 on every source PR: resolved by this single block.

### Gates

Re-run on the final code commit 669e188 (handoff-only commits after it): ruff check
  "All checks passed!", ruff format --check "211 files already formatted", mypy src "Success: no
  issues found in 87 source files", pytest "154 passed".
