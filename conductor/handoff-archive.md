# Handoff Archive

Older handoff blocks moved out of the thin active log (`handoff-log.md` keeps the current block only — conductor/AGENTS.md).

## 2026-07-18 — bughunt/find-field-truncation-flag

**What changed:** Fixed the `strata_find_field` truncated-flag off-by-one in
`src/strata/mcp/tools.py`. `len(matches)` can never exceed the 50-item cap, so
`"truncated": len(matches) >= 50` wrongly reported `truncated=true` at exactly
50 matches (nothing was actually omitted). Now a `total` counter is
incremented for every match while `matches` still only appends the first 50;
`truncated = total > 50`.

**What was verified:**
- Added `test_strata_find_field_truncated_flag_false_at_exactly_fifty_matches`
  (50 matches → `truncated is False`).
- Negative control: stashed the source fix (kept the test) and confirmed the
  new test fails against the old `>= 50` logic.
- Full suite: 105 passed. `ruff check` and `mypy` clean on changed files.

**What remains / exact next step:**
- Direct push to `bughunt/find-field-truncation-flag` is blocked — it is
  currently this repo's default branch, and ruleset `main`
  (targets `~DEFAULT_BRANCH`, no bypass) requires all changes to land via PR.
  Opened PR #13 (`bughunt/find-field-truncation-flag-fix-truncated-boundary` →
  `bughunt/find-field-truncation-flag`) to carry the commit onto this branch;
  merging #13 updates PR #9 automatically. Left a status comment on PR #9;
  did not resolve the Codex thread there (out of scope for this task).
- Operator action needed: merge PR #13 (dispatched agents don't merge).

## 2026-08-16 — feat/pypi-strata-lookml

Commit: 117f9fb (pre-merge branch anchor — this repo squash-merges, so branch SHAs do
  not survive the merge; post-squash, resolve the landed anchor deterministically via
  `gh pr view 18 --json mergeCommit -q .mergeCommit.oid` and treat THAT as this block's
  commit for any HEAD reality check)
Conductor Mode: slice
Context Budget: medium
Context Loaded: AGENTS.md, conductor/AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/index.md, conductor/slice-04-pypi-packaging.md, handoff-log latest block.
Context Skipped: handoff-archive.md.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no stable tag required (first `v0.1.6` tag is the post-merge publish trigger, operator-pushed).

**Governing spec:** `conductor/slice-04-pypi-packaging.md` (authored at the review gate's
direction — PR #18 Codex P1 — as the in-repo contract for this work).

**What changed:** Packaged strata-oss for PyPI distribution as `strata-lookml`
(the names `strata` and `strata-mcp` are taken on PyPI by unrelated projects; the tool stays
"Strata" everywhere, console scripts `strata`/`strata-mcp`/`strata-chart` unchanged).

- `pyproject.toml`: `name = "strata-lookml"`, version `0.1.5` → `0.1.6`, and — found during
  head-side verification — **`mcp>=1.0,<2`**: mcp 2.0 removed `mcp.server.fastmcp`, which
  `src/strata/mcp/server.py` imports, so the previous unbounded pin made every fresh install
  pull an SDK the server cannot import (`strata-mcp` dead-on-arrival while the other two
  commands worked). Upper-bounded with an in-file comment; the 2.x migration is follow-up work.
- `src/strata/cli/main.py`: `click.version_option(package_name="strata-lookml")` — Click
  resolves installed metadata by exact distribution name; the stale `"strata"` made
  `strata --version` raise post-rename (PR #18 Codex P2).
- `.github/workflows/release.yml`: `publish-pypi` job (needs `build-and-release`) using PyPI
  Trusted Publishing (OIDC) via `pypa/gh-action-pypi-publish@release/v1` — no stored token;
  artifact handoff so publish consumes the already-built `dist/`; `.mcpb` bundle
  (`@anthropic-ai/mcpb` → `mcpb validate` → `mcpb pack`) attaching `strata-lookml.mcpb` to
  the GitHub Release.
- New `mcpb/` dir: spec-conformant `manifest.json` (`server.type: uv`, manifest 0.4), minimal
  `pyproject.toml` depending on `strata-lookml>=0.1.6`, 2-line `src/server.py` shim (the
  `.mcpb` `uv` runtime requires a local entry-point file; there is no published-package mode).
- `README.md`: Installation section (`uvx --from strata-lookml strata-mcp` — a bare
  `uvx strata-lookml` fails, no script matches the distribution name; `pipx`), Cursor +
  VS Code one-click install badges, top-of-file naming-split note.
- `.gitignore`: `*.mcpb`.
- Conductor: `slice-04-pypi-packaging.md` authored (status `review`), prior 07-18 handoff
  block moved to a new `conductor/handoff-archive.md`, `index.md` Active Slice pointer
  updated.

**What was verified — two-stage, honestly split:**

*Dispatch stage (sandboxed, no outbound network):* static only — TOML/JSON/YAML parsed,
`py_compile` clean, manifest hand-diffed against the live `modelcontextprotocol/mcpb` spec,
README regexes for `tests/test_docs_consistency.py` re-run by hand. Build/test explicitly
NOT run; disclosed rather than claimed.

*Head-side stage (full network, 2026-08-16):*
- `python -m build` → sdist + wheel build clean.
- **Fresh-venv wheel install** → `strata --version` reports `strata, version 0.1.6` (the P2
  fix, proven against installed metadata); `strata-chart` resolves; `strata-mcp` imports
  clean. This check is what CAUGHT the mcp 2.0 resolver break (resolver pulled mcp 2.0.0,
  `from mcp.server.fastmcp import FastMCP` failed; re-pinned `<2` → resolver picks 1.29.0,
  import clean, rebuilt + re-proven end-to-end).
- Full suite on an editable `[dev]` install: **106 passed**. `ruff check` clean on touched
  Python.
- Still unverified until the first tag push: the `publish-pypi` and `.mcpb` steps
  end-to-end (they can only run in CI on a tag) — watch that run, don't assume green.

**Operator prerequisite (blocking, before the first tag push):** configure the PyPI Trusted
Publisher at pypi.org — project `strata-lookml`, owner `G-Schumacher44`, repo `strata-oss`,
workflow `release.yml`, environment `pypi`. Without it `publish-pypi` fails closed with an
OIDC error — expected, not a bug (see the comment in `release.yml`).

**Also fixed on this branch (found by Apollo's required-checks blocker):** the
`tests/lookml/gcs_analytics` submodule pinned `cd9a4deb`, a commit its upstream no longer
has — the playground repo was recreated during the 2026-07-12 public bootstrap, orphaning
the pin, and `strata-ci` had never once run on `main`, so every PR checkout has been failing
at `actions/checkout` before tests could run. Repointed to the upstream head `f32aafa0`
(the playground's actual content — its repo holds 2 commits total). Suite re-run at the new
pin: 106 passed. Same dangling-ref shape as the pre-squash `anchor_ref` bug, third instance
of bootstrap-era rot (README URLs, default branch, now this).

**Panel round (operator-ordered pre-merge review: twins + philosophers, 2026-08-16):**
five parallel read-only reviewers. Verdicts: artemis SHIP · apollo ACCEPT · diogenes LEAN ·
socrates GO-WITH-GUARDRAILS · plato NEEDS-FORM (1 blocker). All findings addressed in one
batch commit:

- **plato BLOCKER — the self-targeting mirror job:** `release.yml` still carried the
  bootstrap-era `sync-to-oss` job. After this repo became canonical, that job SELF-TARGETED:
  on the same `v*.*.*` trigger as the release, it added this very repo as remote `public`,
  `git rm`'d every `.publicignore` path (including `conductor/handoff-log.md` and
  `slice-04` — files this PR wrote), and pushed the result onto our own `main`, with
  workflow-wide `contents: write` making `GITHUB_TOKEN` sufficient. The documented next
  step (push `v0.1.6`) would have fired it. **Job deleted** (history note left in the file);
  `docs/public-release.md` + `.github/workflows/public-release-audit.yml` (mirror-era,
  `public-v*`-triggered) deleted; `scripts/README.md` row updated. Residue
  (`.publicignore`, `scripts/check_public_release.py` + its tests) left for a follow-up
  issue — inert without the workflows, and removing the tests would churn suite counts in
  an already-long PR.
- **socrates + artemis (independently converged) — the blank PyPI page:** `pyproject.toml`
  had no `readme`, no `classifiers`, no `[project.urls]` — the built wheel's METADATA had
  ZERO Description; v0.1.6's page would have published blank and immutable. All three added;
  README's 8 relative image paths absolutized to `raw.githubusercontent.com` (PyPI does not
  rewrite relative paths); `[tool.hatch.build.targets.sdist]` added (anchored `/`-patterns —
  bare names glob at any depth; sdist went 317 files/6.8MB → 173 files, zero stray dirs);
  `mcp-name: io.github.g-schumacher44/strata` marker added for the future registry listing.
- **diogenes:** authoring-process "verification note" removed from the user-facing README
  (already recorded here).
- **plato should_fix:** pipx command-collision sentence added to the README naming note
  (the unrelated `strata-mcp` package installs a `strata` command; pipx shares one bin/).
- **notes:** `mcpb/README.md` stale step name fixed; `conductor/index.md` template-leftover
  header ("my-looker-project") fixed; `docs/README.md` dead `security-review.md` link fixed.
- **apollo hygiene:** `tests/test_mcp_tools.py` ruff-format (commit f331f1d) is hereby
  claimed in this log — it was changed-but-unclaimed in the earlier bullet list.

Re-verified after the batch: wheel METADATA carries Description (29.6k chars) + 7
classifiers + 3 Project-URLs with absolute image URLs; fresh-venv install → all three
commands; suite 106 passed; `ruff format --check` + `ruff check` clean tree-wide;
`release.yml` still valid YAML.

**Codex round 2 (post-panel head, 4 findings, all addressed):**
- *P1 release ordering:* the GitHub Release was created in the build job, BEFORE
  publish-pypi ran — a failed/misconfigured publish would leave a public Release whose
  `.mcpb` cannot start (its shim resolves `strata-lookml` from PyPI at launch).
  `release.yml` restructured to three jobs: `build` → `publish-pypi` → `github-release`;
  the Release now exists only after PyPI has the package. This also closes artemis's
  earlier first-minute-race note for good.
- *P2 shim pin:* `mcpb/pyproject.toml` pinned `strata-lookml==0.1.6` (was `>=0.1.6`,
  which would silently execute newer code under an artifact advertising 0.1.6).
- *P2 tag/version guard:* new fail-closed `Verify tag matches all version fields` step —
  refuses to build/publish when the tag disagrees with pyproject.toml, mcpb/manifest.json,
  or the shim pin. Proven both directions locally: passes at 0.1.6, refuses a wrong tag
  (negative control).
- *P1 Commit anchor:* the `Commit:` field below now carries a real seven-char hash
  (maintained one-behind by construction: the anchor names the last substantive commit;
  the anchor update itself is a docs-only commit).

Release procedure consequence, now that versions are pinned in three places: a release
bump touches pyproject.toml + mcpb/manifest.json + mcpb/pyproject.toml together, and the
guard refuses the tag if any is missed.

**Exact Next Steps:**
1. Operator: configure the PyPI Trusted Publisher (above), then merge PR #18.
2. Operator (or Koa on instruction): push tag `v0.1.6` — first end-to-end proof of
   publish-pypi + `.mcpb`; watch the run.
3. Post-publish: `uvx --from strata-lookml strata-mcp` against a real MCP client once
   (closes the last slice-04 acceptance box); spot-check the Cursor/VS Code badges.
4. Follow-up (separate slice): migrate `src/strata/mcp/server.py` off `mcp.server.fastmcp`
   so the `<2` pin can lift; then registry submissions (official MCP registry, awesome-lists)
   per the distribution research (koa library, 2026-08-16).

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

**Codex round 2 (P2, addressed):** the zombie verdict's `evidence_ids` cited only the PDT
node + build record while the verdict actually rests on every consumer's dead-code entry —
an un-auditable verdict in a dual-evidence tool. `_pdt_ledger` now appends
`dead:explore:<model.explore>` for each consumer on zombie records (same convention the
dead-views records already use), and the regression test asserts the full trail per zombie
plus a negative control (a `used` PDT must carry NO dead-explore evidence). Suite 107 passed.

**Codex round 3 (P2, addressed the thorough way):** correcting the alt text to "14" while
the PNG still visibly rendered "SCHEMA DRIFT 10" made the accessibility description lie about
the image. Rather than revert the text, the three dashboard screenshots were REGENERATED from
this branch's code (headless Chrome over CDP, enterprise_mono fixtures, original dimensions)
— and doing so surfaced one more real bug: the dead-code register names explores
MODEL-QUALIFIED while graph labels are bare, so `_build_graph_data`'s bare-name lookup missed
every dead explore — they rendered green/KEEP with QUERY COUNT 0 visible. Fixed at the single
source (qualified lookup in `_build_graph_data`; the tap handler now reads the node's own
`dead` flag instead of re-deriving), pinned by `test_graph_marks_dead_explores_dead` with a
live-explore negative control (verified: all 13 dead/zombie nodes flag). New screenshots show
the truthful state — dead_finance_v2 red with DEPRECATE, both zombie PDTs purple-badged with
their $-figures and dead consumers — and all three alt texts now describe exactly what the
images render. Suite 108 passed.

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
