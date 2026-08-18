# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-08-17 — fix/audit-remediation-0.1.7

Commit: e8152aa (pre-merge branch anchor — this repo squash-merges, so branch SHAs do not
  survive the merge; post-squash resolve the landed anchor via
  `gh pr view 21 --json mergeCommit -q .mergeCommit.oid` and use THAT for any HEAD check)
Conductor Mode: full (escalated per CONDUCTOR_MODES.md triggers: root governance docs edited; cross-layer L1→MCP→outputs)
Context Budget: medium
Context Loaded: AGENTS.md (full authority order), conductor/CONDUCTOR_MODES.md, conductor/index.md, conductor/README.md, conductor/slice-05-audit-remediation.md, handoff-log latest block, docs/ files under edit, code seams (l1/enrich.py, mcp/server.py, outputs/dashboard.py). intent.md: not present in this repo's public tree (mirror-era exclusion) — noted rather than silently skipped.
Context Skipped: handoff-archive.md older entries.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no stable tag required; no tag pushed this slice (0.1.7 version bump only, prep for a future tag).

**Governing spec:** `conductor/slice-05-audit-remediation.md` (authored this session at the
operator's direct order — a claim-by-claim docs-vs-code audit of the just-published package
found 12 non-confirmed findings + 2 filed issues, all ordered fixed in one PR).

**What changed:** See commit e8152aa's message for the full breakdown. Summary:

- **The one real code fix (audit #22, README's flagship claim):** `l1/enrich.py`'s
  `pdt_ledger` status now computes a genuine `zombie` value — a PDT with real build facts
  and real consumers where every consumer is itself in the dead-code register. Previously
  status was set from usage alone and never cross-referenced deadness, so both
  `enterprise_mono` demo zombies (`pdt_attribution_full_funnel`, `pdt_customer_value_score`)
  rendered green "In Use" on the dashboard despite being the exact scenario the README
  advertises. Reuses the existing dead-code register (single source of truth) — does not
  re-derive deadness a second way. Wired through `outputs/dashboard.py` (distinct purple
  zombie badge/color/legend, not the same visual as plain `unused`), `outputs/artifacts.py`
  (cleanup roadmap now flags zombie cost too), and `mcp/tools.py` (additive
  `zombie_pdt_count` in `strata_usage_summary`, `unused_pdt_count`'s existing meaning left
  intact for backward compat).
- **serverInfo version (Closes #20):** `mcp/server.py` resolved the `mcp` SDK's version
  (1.29.0) in the initialize handshake because FastMCP 1.29's constructor has no `version`
  kwarg (verified by reading the installed SDK source, not guessed) — the low-level
  `Server.version` defaults to `None` and falls back to `importlib.metadata.version("mcp")`.
  Fix sets `server._mcp_server.version` post-construction from
  `importlib.metadata.version("strata-lookml")`, with a `PackageNotFoundError` fallback for
  editable/dev checkouts without an installed distribution record.
- **11 docs-truthfulness corrections** (README, docs/README.md, docs/security-hardening.md,
  docs/testing-findings.md, GOVERNANCE.md, AGENTS.md) — each verified against current repo
  state before editing, not just patched on the audit's say-so:
  - Fixture $ figures ($45,000/$18,750/~$765,000/yr) footnoted as hand-authored
    illustrative values, not products of the $5/TB formula shown beside them (verified: the
    formula applied to the fixture's own `bytes_processed` doesn't reproduce those numbers).
  - "14 domain skills" → 15 (filesystem-verified), **plus** a new generic
    `test_readme_domain_skills_count_matches_filesystem` in `test_docs_consistency.py` that
    regex-matches any `"N domain skills"` phrase and asserts it against the live
    `SKILLS_DIR` count — this class of drift is now machine-caught, not just this instance.
  - `docs/README.md`'s dead "Security Review — 3 HIGH, 6 MED" row deleted (that content was
    removed with the mirror era); Security Hardening row redescribed as what it is.
  - Dashboard screenshot alt text "10 schema drift records" → 14 (current reproducible
    count; matches the doc's own body text elsewhere).
  - `docs/testing-findings.md` Known Gaps: deleted the stale duplicate CTE row marked
    documented/unresolved — verified the fix is real at `resolver.py`'s `_sql_upstreams()`
    (the `✅ fixed` row was already correct).
  - "18 read-only tools" (4 spots) → truthful "18 tools — 17 read-only, 1 sandboxed"
    framing; `strata_render_chart` writes only to `~/.strata/output`/`/tmp`, never the
    LookML repo.
  - `docs/security-hardening.md` notification phrasing aligned with
    `docs/notifications-setup.md`'s honest "stops at payload generation" — verified
    `scripts/notify.py` literally exits 2 without `--dry-run`, no delivery code path exists
    at all (not just "gated").
  - `GOVERNANCE.md` + `AGENTS.md` read-only claims qualified with the same "as part of core
    analysis" carve-out `security-hardening.md` already used — verified `strata bootstrap`
    legitimately writes scaffolding (`conductor/`, `.mcp.json`, config), never `.lkml`.
  - "No false positives before you deprecate" softened to "designed to eliminate" +
    pointer to the FP classes `testing-findings.md` documents as fixed.
  - The unbacked "~82% smaller / ~30 round-trips" figure reworded to a qualitative claim
    (no benchmark script existed to back the precision; chose reword over fabricating one).
  - Haiku benchmark sections in `testing-findings.md` labeled one-off/manual/non-reproducible
    (date 2026-06-06, matching the doc's own stated verification date) instead of implying
    a pinned harness.
- **Mirror residue removed (Closes #19):** `.publicignore`, `scripts/check_public_release.py`,
  its test, and the `scripts/README.md` row — inert since PR #18 deleted the `sync-to-oss`
  workflow job that was their only consumer. Also cleaned two dangling comment references to
  `.publicignore` in `tests/test_mcp_tools.py` and `tests/fixtures/conductor/index.md` (same
  mirror-era rationale, now stale regardless of the file's existence).
- **Version bump to 0.1.7:** `pyproject.toml`, `mcpb/manifest.json`, `mcpb/pyproject.toml`
  shim pin, all together. Ran `release.yml`'s "Verify tag matches all version fields" Python
  block locally, verbatim: passes against tag `0.1.7`, refuses (exit 1, all three mismatches
  reported) against a wrong tag `0.1.8` — both directions proven, no tag pushed.

**What was verified:**
- Full suite: **106 → 107 passed** (removed 4 mirror-era tests with the D deletions; added
  5: `test_zombie_pdt_detection_enterprise_mono`, negative control
  `test_pdt_ledger_unused_status_unaffected_by_zombie_detection`, two in new
  `tests/test_mcp_server.py` for the serverInfo fix, one docs-consistency domain-skills-count
  test). Ran with `.venv/bin/pytest` against a fresh `uv venv` + `pip install -e ".[dev]"` —
  no prior `.venv` existed in this checkout.
- `ruff check src/ tests/ scripts/`: clean. `ruff format --check`: 173 files already
  formatted, clean.
- `mypy src/strata --ignore-missing-imports`: clean, 87 source files.
- `release.yml` re-parses as valid YAML after the historical-comment area was left untouched.
- Manually confirmed both `enterprise_mono` zombie PDTs report `status: "zombie"` via a
  direct `build_graph` + `build_dashboard_html` run, and that the rendered HTML contains
  both the `zombie-badge` CSS class and the `"status": "zombie"` JSON payload — not just
  asserted via the test, independently eyeballed the actual artifact.
- Confirmed `create_server(...)._mcp_server.version` reports the installed `strata-lookml`
  version (0.1.6 in this dev checkout, will be 0.1.7 once released) and is provably
  different from `importlib.metadata.version("mcp")` (1.29.0).

**Judgment calls beyond the literal task list (disclosed, not hidden):**
- Extended `outputs/artifacts.py`'s cleanup-roadmap condition from `status == "unused"` to
  `status in ("unused", "zombie")` — the roadmap's whole purpose is surfacing PDT cost for
  review, and leaving zombies out of it while fixing the ledger/dashboard would have been
  the same undercount bug relocated one hop over. No test pinned the old narrower behavior.
- Added `zombie_pdt_count` to `strata_usage_summary` as a new additive field rather than
  redefining `unused_pdt_count`'s existing meaning — avoids a silent breaking change to an
  already-published MCP tool contract for external consumers reading that field today.
- Did not touch `src/strata/skills/governance/strata_workflow.md`'s "zombie = unused OR
  dead-backed" framing (lines ~216-221) — it predates this fix, is now literally closer to
  true than before, and wasn't in the audit's 12-item list; flagging here rather than
  silently expanding scope.

**Pre-gate ritual:** run via `koa review --branch` before push, per the dispatch's mandatory
gate instructions — see PR body for the run's disposition (pass/findings-disclosed).

**Exact Next Steps:**
1. Operator: review and merge this PR (Closes #19, closes #20).
2. Operator (or Koa on instruction): once ready for a real release, push tag `v0.1.7` —
   this is the first tag since 0.1.6's publish; watch `publish-pypi` + `.mcpb` attach.
3. Post-merge: resolve this block's `Commit:` anchor to the squashed merge commit via
   `gh pr view <PR#> --json mergeCommit -q .mergeCommit.oid` (this repo squash-merges,
   branch SHAs don't survive) — update in the next docs-only commit, per convention.
4. Optional follow-up (not blocking, noted above): decide whether
   `strata_workflow.md`'s zombie-definition framing should be tightened now that the code
   emits a real `zombie` status distinct from `unused`.
