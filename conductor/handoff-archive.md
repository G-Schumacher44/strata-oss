# Handoff Archive

Older handoff blocks moved out of the thin active log (`handoff-log.md` keeps the current block only — conductor/AGENTS.md).


## Date: 2026-11-08 — feat/dashboard-polish (dashboard redesign: graph legibility + polish)

Commit: 630bbee
  (Implementation commit; the PR squash-merges. After the merge, resolve the landed anchor with `gh pr view <n> --json mergeCommit`.)
Conductor Mode: feature — dashboard presentation only; no artifact/schema change.
Context Budget: medium
Context Loaded: AGENTS.md, outputs/AGENTS.md, conductor/dashboard-north-star.md, handoff-log, dashboard.py, cli/dashboard.py, escaping guardrail + dashboard tests.
Exact Next Steps: operator approved the preview ("way better"); PR open on the twin gate, operator merges. Follow-ups are listed in the PR body (light theme, graph below the findings, phone card tables, whether the attention filter counts PDTs without build data).

### What changed

- Dependency graph: left-to-right layers (explores, views, PDTs/tables) with layer headers; short labels that fade below readable zoom and always show for the hovered/selected neighborhood; per-kind shapes (explore circle, view pill, PDT diamond, table barrel) and a halo on problem nodes; unconnected nodes laid out in their own row; canvas sized to the tallest layer; hover tooltip with the full name; search (name/model), per-kind toggles, a "Needs attention" filter, zoom-to-selection and reset; clickable upstream/downstream lists and a start-here list of problem nodes in the detail panel. Plain wheel scrolls the page; pinch or Cmd/Ctrl-wheel zooms (touch keeps native pinch).
- Single source for status colors: `NODE_PALETTE`/`EDGE_PALETTE` in dashboard.py are stamped onto nodes and emitted as `--n-*`/`--e-*` CSS tokens the legend, badges and PDT chart read. Tests now assert against the palette keys plus a distinctness check.
- New `attention` node flag (Python-side) drives the filter and start-here list. Note: in both fixtures every zombie/unused node is already `orphan`, so the status clause of the flag is belt-and-braces and not independently exercised by fixture data.
- Page polish: sticky section nav, data-driven headline naming the costliest problem, KPI cards ordered by severity and linking to their sections, sentence-case labels, sortable tables with sticky headers inside scroll containers, PDT ledger sorted by cost with palette-coloured chart, responsive to 390px (iframe-verified; headless Chrome cannot size a window below ~500px).
- Codex P2 on #65: without usage/schema facts the page claimed "This repo is clean." `l1.enrich.analysis_coverage(graph)` (one source, keyed on each enrichment step's own marker: `dead_code` / `schema_drift`) is embedded as `COVERAGE`; the headline, KPIs and empty states read it and say "not run" instead of clean/0. Headline/KPI wording lives in pure JS functions (`heroCopy`, `kpiCards`) that the test runs in node against real artifacts.
- Codex round 3 on #65: (a) spec B3/D13 folded in: `strata_usage_summary` serializes one explore population (`ir_explore_count`, `dead_explore_count`, `dead_view_count`, `active_explore_count` = ir − dead, `None` when usage unchecked); the KPI shows it instead of JS subtraction from usage rows (which went negative for unqueried explores). (b) a search/attention change clears a pinned selection; graph highlight state now lives in top-level `newGraphState`/`setGraphFilter`/`graphFilteredSet`/`applyGraphState`, tested in node against the vendored headless Cytoscape.
- `strata dashboard` serves dashboard.html at `/` (Host check still runs first; artifacts stay at their paths).

### Gates

ruff check + format --check clean, mypy clean, pytest 217 passed (209 before; +2 root-route host tests, +2 palette/attention tests, +2 coverage/not-run tests, +2 explore-population/pinned-filter tests), dashboard JS `node --check` pass. Negative controls: population test fails with the old JS subtraction, with a usage-row population, and pre-fix; pinned-filter test fails without the pin clear and pre-fix; not-run test fails with the clean-headline gate removed, with KPI coverage forced on, and against the pre-fix dashboard; root-route test fails with the rewrite removed; legend-token test fails with a hand-copied hex; attention test fails with the flag removed.

## Date: 2026-11-08 — docs/claims-match-code (docs match the code)

Commit: 17fa07b
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view 64 --json mergeCommit`.
Conductor Mode: patch — docs/help text only, no version bump.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log latest block, cli/mcp.py, cli/generate_schema.py, cli/validate.py, mcp/tools.py, docs/security-hardening.md, docs/enterprise-deployment.md, workflows.
Exact Next Steps: operator merges after the gate passes; no follow-up work.

### What changed

Four doc claims the code did not back, corrected without behavior change: (1) `strata mcp` help, GOVERNANCE.md and mcp/AGENTS.md said the MCP tools are all read-only; 17 are, `strata_render_chart` writes one HTML file under `~/.strata/output/` or `/tmp/` (path guard in mcp/tools.py). (2) security-hardening.md and enterprise-deployment.md listed Slack/Jira tokens as GitHub secrets; delivery is not implemented (scripts/notify.py) and no workflow references them, so the rows are removed. (3) enterprise-deployment.md called Conductor handoffs the audit trail; now described as a convention (`strata validate` only checks the `Commit:` hash exists). (4) generate-schema and its docs said ADC; the `bq` CLI uses gcloud's own credentials (`gcloud auth login`), per Google's BigQuery auth docs — help, the bq-missing hint, the dry-run hint, the schema script, cli-guide, two skills and README updated.

### Gates

Full pytest 205 passed (submodules initialized); ruff check, ruff format --check, mypy src clean. No test asserted the changed strings.


## Date: 2026-11-08 — fix/escaping-callback-scope (scope callback index vars)

Commit: cc9bb22
  (Implementation commit; the PR squash-merges, post-merge resolve the landed anchor with
  `gh pr view 63 --json mergeCommit`.)
Conductor Mode: patch — no version bump.
Context Budget: low
Context Loaded: AGENTS.md, conductor/AGENTS.md, handoff-log latest block, tests/test_l1_synthesis_outputs.py.
Exact Next Steps: operator merges after the gate passes; no follow-up work.

### What changed

Test-only. The escaping guardrail no longer trusts a `forEach/map` callback index block-wide; it is trusted only inside that callback's body (callback body spans, placeholders carry source offsets, `.map` bodies checked with the index added only for that body). Closes #31.

### Gates

New scoped/still-trusted tests; re-adding block-wide trust makes the scoped test fail. ruff check/format, mypy src clean; full pytest 183 passed (submodules initialized).

## Date: 2026-11-08 — fix/validate-active-slice (validate Active slice annotation)

Commit: 4db71ea
  (Implementation commit; the PR squash-merges, post-merge resolve the landed anchor with
  `gh pr view 62 --json mergeCommit`.)
Conductor Mode: patch — no version bump.
Context Budget: low
Context Loaded: AGENTS.md, conductor/AGENTS.md, handoff-log latest block, cli/validate.py, tests/test_cli.py.
Exact Next Steps: operator merges after the gate passes; no follow-up work.

### What changed

`get_active_slice_rel` in `cli/validate.py` used the whole remainder of the `Active slice:` line as the path, so index.md's annotation (`path.md (review — PR open; ...)`) failed the check. It now takes the first whitespace-delimited token (backticks stripped); the `none` sentinel and genuine missing-file failure are unchanged. `strata_conductor_status` still returns the full line as status text. Closes #47.

### Gates

New tests in tests/test_cli.py (plain, annotated, backticked, missing-file); with src reverted 3 fail. ruff check/format, mypy src clean; full pytest 185 passed (submodules initialized).

## Date: 2026-11-08 — fix/list-orphans-kind (narrow strata_list_orphans kind)

Commit: c17676f
  (Implementation commit; the PR squash-merges, post-merge resolve the landed anchor with
  `gh pr view 59 --json mergeCommit`.)
Conductor Mode: patch — no version bump.
Context Budget: low
Context Loaded: AGENTS.md, conductor/AGENTS.md, handoff-log latest block, mcp/tools.py, mcp/server.py, cli/query.py, README.
Exact Next Steps: operator merges after the gate passes; no follow-up work.

### What changed

`strata_list_orphans(kind=...)` accepted `explore|field` but only view orphans are recorded, so those kinds always returned `[]` (readable as "none exist"). Narrowed to `all|view`; other values raise `ValueError` with an explicit message. MCP tool schema (`Literal`), CLI `--kind` choice, and README table kept consistent. Closes #49.

### Gates

New `test_strata_list_orphans_rejects_unsupported_kind` fails with src reverted (3 failed), passes with the fix. ruff check/format, mypy src clean; full pytest 184 passed (submodules initialized).

## Date: 2026-11-08 — fix/chart-output-path (chart output: no fixed /tmp path, no symlink following)

Commit: 4afba41 (initial fix; review-round fixes follow it. The PR squash-merges; post-merge resolve
  the landed anchor with `gh pr view 61 --json mergeCommit`.)
Conductor Mode: patch — security hardening, no new tool or layer change.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, viz/render.py, cli/chart.py, mcp/tools.py, l1/looker.py
  (the #58 O_NOFOLLOW pattern), docs/security-hardening.md.
Exact Next Steps: operator merges after twins/Codex pass; CHANGELOG Unreleased > Security rides the
  next tag.

### What changed

- `render_chart(out_path=None)` defaults to a fresh `mkstemp("strata_chart_*.html")`; explicit
  paths are opened with `O_NOFOLLOW` (`_write_html`). Where `O_NOFOLLOW` is absent, an lstat
  (`is_symlink`) check refuses a symlink instead.
- `strata chart` / `strata-chart` `--out` no longer defaults to `/tmp/strata_chart.html`.
- MCP `strata_render_chart` resolves only the parent dir and refuses a final-component symlink
  before the root check, so confinement does not depend on `O_NOFOLLOW`.
- `strata query navigate --chart` goes through `strata_render_chart`, so it is covered.

### Verification

- New tests in `tests/test_security.py` (fresh default, normal write, symlink refused in
  render_chart + MCP, symlink refused with `O_NOFOLLOW` monkeypatched away). Reverting `src/`
  makes the behavior tests fail; restored, all pass.
- Full suite 186 passed (with test submodules initialised), ruff, ruff format, mypy clean.

## Date: 2026-11-08 — fix/dashboard-host-check (DNS-rebinding guard on `strata dashboard`)

Commit: e73ccd9 (first implementation commit; review-fix commits follow. The PR squash-merges;
  resolve the landed anchor with `gh pr view 60 --json mergeCommit`.)
Conductor Mode: patch — one security fix, no new tool, no layer-boundary change.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log, cli/dashboard.py, docs/security-hardening.md.
Exact Next Steps: operator merges after the gates pass; the fix rides the next release.

### What changed

- `cli/dashboard.py`: `allowed_hosts(port)` / `make_handler(port)`. The handler answers 403 (no
  artifact content) unless `Host` is `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>`
  (case-insensitive); on port 80 the port-less forms are also accepted, since browsers omit the
  default port. Allowlist only; enforced in `send_head` (GET + HEAD).
- `tests/test_dashboard_host.py`: loopback forms served; foreign, wrong-port, port-less, empty and
  missing Host refused; port-less accepted only for port 80.
- `CHANGELOG.md` (Unreleased > Security), `docs/security-hardening.md` (Network Surface).

### Verification

- Negative control: with the allowlist check disabled, the refusal tests fail (7 of the first 11).
- Gates (with submodules initialized): pytest, ruff check, ruff format --check, mypy src.

## Date: 2026-11-04 — fix/security-0.1.9 (security hardening before the 0.1.9 tag)

Commit: 39be7b8 (the fix commit; the docs commit and any review fixes follow it. The PR squash-merges; post-merge resolve
  the landed anchor with `gh pr view <this PR> --json mergeCommit`.)
Conductor Mode: patch — security fixes from a read-only audit at origin/main 9d19e42, plus the
  docs that describe them. No new MCP tool, no layer-boundary change.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, generate_schema.py + scripts/generate_schema_facts.py,
  l1/looker.py, cli/auth.py, cli/mcp.py, mcp/server.py + ir/store.py, viz/render.py,
  mcp/tools.py, cli/dashboard.py, ir/parser.py, SECURITY.md, docs/security-hardening.md,
  docs/enterprise-deployment.md, README security sections.
Grounding: Looker OAuth guide https://docs.cloud.google.com/looker/docs/api-cors (auth on the UI
  host with client_id/state/S256 challenge; JSON POST to /api/token on the API host; redirect
  URIs matched exactly; registration via Admin or register_oauth_client_app with group_id; no
  refresh request documented). bq `--parameter` ARRAY syntax and the identifier limitation:
  https://docs.cloud.google.com/bigquery/docs/parameterized-queries. `--max_rows` default 100 and
  `--maximum_bytes_billed`: https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference.
Exact Next Steps: operator merges after twins pass -> tag v0.1.9 per the previous handoff (now in
  handoff-archive.md). First real Looker login is the live validation of the OAuth flow; until
  then the docs label it "not yet validated against a live instance".

### What changed

- generate-schema: one source for query construction (`build_columns_query`), shared by the CLI
  and the script; identifier allowlist; table names as `@names` ARRAY parameter; bytes/rows caps.
- Looker OAuth: new `l1/oauth.py` (PKCE, state, `code_from_callback`, `LoopbackReceiver`);
  `auth login` loses `--code`, gains `--api-url`, `--client-id` (alias `--client-guid`),
  `--timeout`; `--no-browser` = paste-on-stdin.
- Token: `LookerToken.ensure_usable_for` is the single origin+expiry check, run at runner
  construction and per request; redirects refused via a no-redirect opener; refresh token not
  stored; atomic 0600 write, 0700 dir; loose perms refused.
- D-1..D-4 local hardening (cache age, stdout in MCP, .html, 127.0.0.1 bind, symlink skip).

### Design calls (conservative options taken)

- Fixed loopback port 48765, not ephemeral: Looker matches registered redirect URIs exactly.
  BREAKING for anyone who registered the old 8765 URI; CHANGELOG says so.
- Refresh token dropped rather than stored unused (no documented refresh grant).
- Token directory: create missing dirs 0700 and keep `~/.strata` 0700, but never chmod any other
  existing directory — a custom `--token-path` in a group/other-accessible directory is refused,
  checked before the browser opens (a code is single-use).
- `--max_rows` raised to 1,000,000: the bq default of 100 truncated column inventories — a
  pre-existing correctness bug fixed in passing because the argv was being rebuilt anyway.

### Pre-gate (local Artemis, FIX-FIRST, no blocker) — dispositions

- Fixed: loopback handler socket timeout (idle connection stalled `--timeout`); stray/forged-state
  callbacks now get 400 and the login keeps waiting; non-ASCII `state` compared as bytes;
  exclusive bind on Windows (`SO_EXCLUSIVEADDRUSE`, no `SO_REUSEADDR`; POSIX keeps
  `SO_REUSEADDR` so a retry can rebind during TIME_WAIT — Codex P2 on PR #58); token-dir rule above; origin-binding
  error names the API URL to pass; `outputs`/`dashboard` map token/API refusals to CLI errors via
  one helper (`cli/outputs.py:live_looker_graph`); docs' write table completed (build, chart,
  query navigate, conductor, validate log, clean deletions) and listener wording made exact.
- Filed as pre-existing (not this PR): dashboard Host-header / DNS-rebinding; `/tmp` chart writes
  follow symlinks.

### Gates

Final tree (head of this branch; also in the PR body):
  ruff check src/ tests/ scripts/ -> "All checks passed!"
  ruff format --check src/ tests/ scripts/ -> "176 files already formatted"
  mypy src/strata_lookml --ignore-missing-imports -> "Success: no issues found in 88 source files"
  python -m pytest -> "181 passed" (157 before this branch)
  python scripts/check_dashboard_js_syntax.py -> "5 generated <script> block(s) passed node --check"
Negative controls: every security guard reverted one at a time -> its test fails (18/18, plus
  the POSIX reuse-address and localhost-refusal controls added in review).
CI round 2 (e701a84): Artemis SHIP (one should_fix: `localhost` redirect vs IPv4-only listener ->
  fixed, receiver now accepts only 127.0.0.1); Apollo ACCEPT (note: gate lines not visible to it
  -> now inlined here); Codex P2 (POSIX SO_REUSEADDR) fixed + resolved.

## Date: 2026-11-04 — docs/legal-0.1.9 (legal-readiness docs + shipped third-party notices)

Commit: e6da3ab (implementation commit; the PR squash-merges, resolve the landed anchor with
  `gh pr view 55 --json mergeCommit`.)
Conductor Mode: patch — docs + packaging metadata only, no src/ Python change, no version bump.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log latest block, pyproject.toml, README.md, CONTRIBUTING.md,
  docs/testing.md, docs/testing-findings.md, docs/runbook.md, src/strata_lookml/assets/js/.
Context Skipped: slices; src/ Python.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: unchanged — v0.1.9 is tagged only after the security-hardening PR also lands.
Changes: THIRD_PARTY_LICENSES (repo root + src/strata_lookml/assets/, so it ships in the wheel;
  `/THIRD_PARTY_LICENSES` added to the sdist include) covering the 7 vendored JS bundles plus
  graphlib/lodash inside dagre; README non-affiliation disclaimer + AI-assistance line;
  "synthetic demo fixture" labels on dollar figures (README, docs, skills); fixture provenance
  (thelook = fork of the archived, unlicensed looker-open-source/thelook, test-only, not shipped);
  CONTRIBUTING licensing of contributions (Apache-2.0 inbound=outbound, DCO sign-off).
Exact Next Steps: merge; after the security PR lands, tag v0.1.9 and confirm the built wheel and
  sdist on PyPI contain THIRD_PARTY_LICENSES. Open follow-up: the Vega bundles' smaller
  permissive sub-components (d3-*, vega-themes, vega-tooltip, semver) are noted, not enumerated.

### Gates

`python -m build` OK — wheel has strata_lookml/assets/THIRD_PARTY_LICENSES, sdist has both
copies and no tests/ fixtures; tests/test_docs_consistency.py 5 passed; README fences balanced;
PR CI (test, pr-analysis, review) green.

## Date: 2026-11-04 — ci/release-mcp-registry-oidc (MCP Registry publish in release.yml)

Commit: eb8ebee (implementation commit; the PR squash-merges, resolve the landed anchor with
  `gh pr view <this PR> --json mergeCommit`.)
Conductor Mode: patch — CI only, no src/ change, no version bump.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log latest block, .github/workflows/release.yml,
  .github/WORKFLOWS.md, the registry's github-actions.mdx.
Context Skipped: slices; src/.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: unchanged — the v0.1.9 tag push now also runs `publish-mcp-registry`
  (needs publish-pypi; OIDC login, mcp-publisher v1.8.7 pinned + cosign-verified).
Exact Next Steps: merge, tag v0.1.9 as already planned, then verify the registry listing for
  `io.github.G-Schumacher44/strata-oss` (registry search or API) instead of running
  `mcp-publisher` by hand. The OIDC publish is only exercised by the real tag run; if it fails
  after PyPI is live, fix forward and re-run the failed job.

### Gates

actionlint on release.yml clean; YAML parse OK; PR CI (test, pr-analysis, review) green.

## Date: 2026-11-03 — chore/release-0.1.9 (version bump, stacked on #46)

Commit: 553889b (the bump commit, on top of #46 head de7af40; review P3 fixes follow it.
  The PR squash-merges; post-merge resolve the landed anchor with `gh pr view <this PR> --json
  mergeCommit`.)
Conductor Mode: patch — version bump + release-guard hardening, no new slice.
Context Budget: low
Context Loaded: AGENTS.md, handoff-log latest block, CHANGELOG.md, pyproject.toml, mcpb/
  {manifest.json,pyproject.toml}, server.json, .github/workflows/release.yml, the #44/#45/#46/#50
  handoffs.
Context Skipped: slices; src/ (no code change).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: RELEASE TRIGGER — after this merges to main, the operator tags `v0.1.9`; the tag
  push runs release.yml (guard -> build -> PyPI -> GitHub Release with the .mcpb).
Exact Next Steps: merge order #45 -> retarget #46 to main, merge -> retarget this PR to main,
  merge -> `git tag v0.1.9 <merge sha> && git push origin v0.1.9` -> verify PyPI 0.1.9 + the
  Release -> registry publish is now automated in release.yml (see the 2026-11-04 block).

### What changed

- 0.1.9 in all five version fields: pyproject `version`, mcpb/manifest.json `version`,
  mcpb/pyproject.toml (shim `version` and the `strata-lookml==0.1.9` pin), server.json top-level
  `version` and `packages[0].version`.
- CHANGELOG: `## [0.1.9] - 2026-11-03` cut from Unreleased (date = PR day; adjust on tag day if
  the tag slips), adding #44 (server.json, mcp-name token, `strata-lookml` script, titles +
  ToolAnnotations) and the ten #50 fixes beside the rename (BREAKING for importers, with the
  `--force-reinstall --no-deps strata` repair) and #46's items. Compare links updated.
- release.yml guard now also checks server.json (top-level and every `packages[].version`, and
  fails when `packages` is empty), so the four version files cannot drift. Still fail-closed: a
  missing file or key raises and exits non-zero under `set -euo pipefail`.

### Gates

Final tree: ruff check "All checks passed!", ruff format --check "211 files already formatted",
  mypy src "Success: no issues found in 87 source files", pytest -q "157 passed" (no new tests;
  the existing registry-manifest test already pins server.json == pyproject version).
Release guard, extracted verbatim from release.yml and run locally: `GITHUB_REF_NAME=v0.1.9`
  -> "tag v0.1.9 matches pyproject, manifest, shim pin, and server.json", exit 0;
  `v0.1.10` -> "VERSION MISMATCH — refusing to publish:" with all five fields listed, exit 1.
  Negative controls on the new leg alone: server.json `packages[0].version` drifted to 0.1.8 ->
  exit 1 naming only that field; `packages: []` -> "server.json has no packages entry", exit 1.
Build: sdist + wheel `strata_lookml-0.1.9`; installed beside `strata==26.0.0`, MCP initialize
  reports serverInfo version 0.1.9, tools/list = 18 (18 titles, 18 annotations, 18 descriptions).

## Date: 2026-11-03 — chore/release-0.1.9-readiness (PR #46, stacked on #45)

Commit: 2aa93bc (last of the six implementation commits; review fixes b6559cc and 027efe1 on
  top, then merges of refactor/import-strata-lookml carrying #44 + the #50 batch. The PR
  squash-merges; post-merge resolve the landed anchor with `gh pr view 46 --json mergeCommit`.)
Conductor Mode: patch — six small, independent changes, one commit each. None changes a layer
  boundary, adds a tool, or alters a tool's behavior (descriptions, `--help`, an escape inside a
  JS comment). Codex asked for Full Conductor; recorded as a judgment call on the PR thread.
Context Budget: medium
Context Loaded: AGENTS.md, conductor/index.md, README.md, pyproject.toml, .github/workflows/*,
  src/strata_lookml/mcp/{server,tools}.py, ir/resolver.py (_mark_orphans), l1/{enrich,schema}.py,
  outputs/dashboard.py, the #44 diff, `gh release view` v0.1.6-v0.1.8.
Context Skipped: slice specs; handoff-archive beyond prepending #45's block.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump here — 0.1.9 rides the stacked `chore/release-0.1.9` PR.
Exact Next Steps: after #45 merges, retarget this PR to main and merge it; then retarget and merge
  the 0.1.9 bump PR and tag v0.1.9.

### What changed

1. README for PyPI: every relative link is an absolute `github.com/.../blob/main/` URL; Quick
   Start opens with `pipx install strata-lookml` (editable install moved to clone-and-try); the
   naming note is corrected (`strata-mcp` 1.0.2 installs a `strata` command, `strata` 26.0.0 has
   no entry points, both ship a top-level `strata/`) and carries the 0.1.8 upgrade repair; PyPI
   strips the badge deep-link schemes; a no-credentials path for your own repo (`query status`,
   `query orphans`, `outputs`).
2. pyproject: PEP 639 SPDX `license` + `license-files` (License classifier dropped),
   `hatchling>=1.27`, keywords, extra classifiers, Documentation/Changelog URLs. No 3.14
   classifier (CI tests only 3.11).
3. CHANGELOG.md (Keep a Changelog): 0.1.6-0.1.8 from the release notes, plus Unreleased.
4. Descriptions for the 8 MCP tools that had none (docstrings only). After the merge every tool
   keeps #44's `title` + `ToolAnnotations` AND has a description; a registry test fails if any
   tool lacks one.
5. `outputs/dashboard.py`: the invalid `\]` escape in a JS comment is now `\\]`; the generated
   template is byte-identical. A test compiles every module with Syntax/DeprecationWarning
   promoted to errors.
6. `strata-mcp --help`/`-h` prints usage and exits 0 without building the graph or opening stdio.

### Not done on purpose

- No version bump (separate stacked PR, after #44's server.json landed).
- No PEP 794 `import-names` field (core metadata 2.5; PyPI/twine support unverified).

### Merge of the updated #45 (#44 + #50 on main)

- Auto-merged with no textual conflicts: #44's decorator lines (`title=`, `annotations=`) and
  #46's docstrings touch different lines of `mcp/server.py`; README and pyproject merged cleanly
  because #45 had already absorbed #44's hunks.
- Handoffs: the per-branch `conductor/handoff/chore-release-0.1.9-readiness.md` is replaced by
  this block; #45's block moved to handoff-archive.md.

### Gates

Final tree (after merging the updated #45): ruff check "All checks passed!", ruff format --check
  "211 files already formatted", mypy src "Success: no issues found in 87 source files", pytest -q
  "157 passed" (154 on #45 + 3 from this PR).
Wheel re-proof beside `strata==26.0.0`: 0 entries under `strata/`, 166 under `strata_lookml/`; all
  four `--help` exit 0 (`strata-mcp --help` prints usage); MCP stdio tools/list = 18 tools, 18 with
  title, 18 with annotations, 18 with a description.

## Date: 2026-11-03 — refactor/import-strata-lookml (PR #45, import rename strata -> strata_lookml)

Commit: 55f4ded (the rename; follow-ups 7d63fa1 mcpb shim, 29a9c5d, 75d5bae upgrade-path note,
  then a merge of origin/main 63cab83 carrying #44 + the #50 batch across the rename. The PR
  squash-merges; post-merge resolve the landed anchor with `gh pr view 45 --json mergeCommit`.)
Conductor Mode: patch — a mechanical, repo-wide rename with no behavior change and no new slice.
Context Budget: medium
Context Loaded: AGENTS.md, conductor/index.md, handoff-log latest block, pyproject.toml,
  .github/workflows/*, mcpb/*, server.json, every file referencing the old package path, and the
  #44/#50 diffs merged in from main.
Context Skipped: slice specs; historical handoff blocks (records of past work keep `src/strata`).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump here — 0.1.9 rides `chore/release-0.1.9` (stacked on #46).
Exact Next Steps: merge #45, retarget #46 to main and merge it, retarget and merge the 0.1.9 bump
  PR, then tag v0.1.9.

### What changed

- `git mv src/strata src/strata_lookml`. The import package `strata` collided with the unrelated
  PyPI project `strata` (26.0.0 ships `strata/__init__.py` and `strata/config.py`); installing
  both in one environment overwrote files.
- Every importer rewritten (src, tests, scripts, mcpb shim, `-m strata.cli.main` subprocess calls,
  the L0 offline-import probe, `src/strata/...` paths in pyproject, CI, GOVERNANCE.md, AGENTS.md,
  docs, README). No `strata` compatibility shim (it would recreate the collision).
- `[project.scripts]` targets moved to `strata_lookml.*`; the names `strata`, `strata-mcp`,
  `strata-chart` and #44's `strata-lookml` are unchanged.
- schema-refresh skill: `python -m strata --help` (never worked, no `__main__`) is now
  `.venv/bin/strata --help`.
- mcpb shim resolves the installed distribution's `strata-mcp` console-script entry point instead
  of importing a module path, so it works against both the 0.1.8 pin and the renamed package
  (Codex P2 on #45).
- Not changed on purpose: the `client_guid=com.gsanalytics.strata.cli` OAuth identifier, the MCP
  server name `strata`, the `.mcp.json` key, `~/.strata/` paths, historical conductor docs.

### Merge of origin/main (#44 + #50 batch)

- Git's rename detection carried every #44/#50 hunk to `src/strata_lookml/`; nothing landed at
  the old path. Five textual conflicts (pyproject scripts, cli/query.py, l1/looker.py,
  tests/test_ir_resolver.py, tests/test_mcp_tools.py) were all new import lines: resolved to
  main's content with `strata.` rewritten to `strata_lookml.`. #44's `strata-lookml` script
  targets `strata_lookml.mcp.server:main`.
- New `from strata...` lines main added in non-conflicting hunks (tests/test_cli.py,
  test_l1_providers.py, test_mcp_tools.py, test_security.py) rewritten by hand; one stale
  comment in cli/skill.py too.
- Handoffs: this repo keeps ONLY handoff-log.md. #45's per-branch file is replaced by this block;
  #44's `conductor/handoff/feat-registry-readiness.md` is folded into handoff-archive.md and
  deleted; the #50 batch block moved to the archive.

### Upgrade path (Codex P2 on #45)

Upgrading 0.1.8 -> the renamed release in an env that also has PyPI `strata` (or `strata-mcp`)
removes the shared `strata/__init__.py` and `strata/config.py` via 0.1.8's RECORD. Repaired by
`pip install --force-reinstall --no-deps strata`. The README naming note carries it; the 0.1.9
CHANGELOG entry carries it too.

### Gates

Final tree after the origin/main merge (706d1ed): ruff check "All checks passed!", ruff format
  --check "210 files already formatted", mypy src "Success: no issues found in 87 source files",
  pytest -q "154 passed" (132 on the pre-merge branch; the rename adds no tests).
Wheel re-proof: 0 entries under `strata/`, 166 under `strata_lookml/`; installed in a fresh venv
  beside `strata==26.0.0`: both import, `strata`/`strata-chart`/`strata-lookml`/`strata-mcp --help`
  exit 0, MCP stdio initialize + tools/list = 18 tools via strata-mcp, strata-lookml and the mcpb
  shim. Local twins: Apollo PASS, Artemis PASS (two P3s fixed: live starter-prompt template paths,
  this gate block).

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

## 2026-11-03 — feat/registry-readiness (PR #44)

Moved here from `conductor/handoff/feat-registry-readiness.md` (folded into the archive by the
#45 update; this repo keeps handoffs in handoff-log.md only). Landed on main as c688a96.

Conductor Mode: patch. Context: research `2026-10-15-positioning-and-adoption.md` (registry + directory readiness). No tool behaviour changed; nothing published.

### What changed
- `README.md`: `mcp-name` token is now `<!-- mcp-name: io.github.G-Schumacher44/strata-oss -->` (was a visible, lower-cased `io.github.g-schumacher44/strata`; registry names are case-sensitive and must equal `server.json` `name`). The ~$45,000/month PDT figure is labelled as hand-authored `enterprise_mono` fixture data.
- `server.json` (new, unpublished): pypi package `strata-lookml` 0.1.8, stdio, `runtimeHint: uvx`.
- `pyproject.toml`: added console script `strata-lookml` (alias of `strata-mcp`) because the registry runs `uvx strata-lookml@<version>`, which needs an executable named after the distribution. Existing commands unchanged.
- `src/strata/mcp/server.py`: all 18 tools get `title` and `ToolAnnotations`. 17 read-only (`readOnlyHint=true`, `destructiveHint=false`, `openWorldHint=false`). `strata_render_chart` is `readOnlyHint=false, destructiveHint=true, idempotentHint=true`: it writes (and may overwrite) one HTML file under `~/.strata/output` or `/tmp`, and the README already calls it the one non-read-only tool. Deviation from "all readOnlyHint true": claiming read-only for a writer would be a false hint.
- Tests: `test_every_tool_has_title_and_explicit_read_only_stance` (allowlist over `list_tools()`, `WRITE_TOOLS` is the only exemption); `test_registry_manifest_matches_package_and_readme` (token matches `server.json` name, versions agree, identifier is a real script). `test_docs_consistency` regex widened for `@server.tool(...)`. Negative controls run: dropping a title, dropping the token each fail.

### Sources (primary)
- Registry PyPI verification, `mcp-name` token rules: modelcontextprotocol/registry `docs/modelcontextprotocol-io/package-types.mdx`
- server.json format and schema `2025-12-11`: `docs/reference/server-json/generic-server-json.md`, `static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`
- GitHub namespace `io.github.<user>/*`: modelcontextprotocol.io/registry/authentication
- Tool `title`, `ToolAnnotations`: MCP spec 2025-11-25 `server/tools` and `schema.ts`
- Claude directory: claude.com/docs/connectors/building/submission (title + readOnlyHint/destructiveHint on every tool; local servers only via a plugin; privacy section required for local connectors)

### Operator steps left (not done here)
1. After merge: bump version to 0.1.9 in `pyproject.toml`, `mcpb/manifest.json`, and `server.json` (both fields) and release to PyPI. The registry reads the README of the PUBLISHED version; 0.1.8 on PyPI carries the old token.
2. `mcp-publisher login github` then `mcp-publisher publish` from the repo root.
3. Claude directory: a plugin bundle (stdio is not accepted as a connector) plus a README "Privacy Policy" section. Not in this PR.
4. Other directories (Glama, Smithery, mcp.so, awesome-mcp-servers) per the research doc.

### Known, predates this PR
- Fresh clones need `git submodule update --init` or `test_pdt_ledger_unused_status_unaffected_by_zombie_detection` fails (fixtures are submodules).

## 2026-08-19 — fix/dashboard-innerhtml-escaping-sweep

Commit: 140f267 (Round 5 implementation commit — see below; this is a squash-merge
  repo, so post-merge the durable anchor becomes `gh pr view 30 --json mergeCommit
  -q .mergeCommit.oid`, but the handoff must anchor to a real commit while the PR is
  open, per Codex PR #30 r1 — a "set once merged" placeholder is not an anchor)
Conductor Mode: patch — single-file bug fix + guardrail hardening, no new slice (per
  `conductor/CONDUCTOR_MODES.md`'s Patch Mode: "bug fix, one-file change"). This repo has no
  `conductor/standard.json` (the koa-spawn HUB-skill governance script skips itself per its
  own instructions when that file is absent); scope came directly from GitHub issue #29 (a
  post-merge Artemis audit of PR #28 / slice-08, commit 6c9eede).
Context Budget: low — single-file bug-fix branch, no new slice.
Context Loaded: GitHub issue #29, src/strata/outputs/dashboard.py (full innerHTML/
  outerHTML/insertAdjacentHTML sweep), tests/test_l1_synthesis_outputs.py (the existing
  `test_data_derived_fields_are_escaped_in_innerhtml_templates` guardrail and its known
  blind spot), .github/workflows/strata-ci.yml (to match CI's gate scope exactly).
Context Skipped: handoff-archive.md beyond moving the completed slice-08 block into it;
  mcp/ and cli/ (out of scope — no CLI wiring touched).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump — pure dashboard-generator fix, no release trigger.

### Round 1 — issue #29, closed this branch

**What changed** (all in `src/strata/outputs/dashboard.py` unless noted):

1. **PDT Ledger "Used By" column** (was line 930) — `explores` local interpolated raw
   `${e}` (explore-key strings) into a nested template before splicing into
   `tr.innerHTML`. Now `${escapeHtml(e)}`.
2. **Migration Impact accordion** (was lines 1083-1085) — all three impact-group lists
   (`views`, `explores`, `fields`) interpolated raw `${v}` map-callback values into
   `content.innerHTML`. Now `${escapeHtml(v)}` in all three.
3. **Full-file sink sweep** (issue #29's item 3) found ONE MORE unescaped sink the
   original ask didn't name: the Cleanup Roadmap's action-label fallback —
   `const [cls, label] = actionStyle[r.action] || ['badge-gray', r.action];` — falls back
   to the raw `r.action` string for BOTH `cls` (CSS class slot) and `label` (visible
   text) when `r.action` isn't one of the three known keys. Both are now wrapped:
   `${escapeHtml(cls)}` and `${escapeHtml(label)}` (cls doesn't strictly need it today —
   every real `actionStyle` value is a literal — but it's derived from the same raw
   fallback as label, and this file's established invariant, per round 14's handoff
   entry, is "every record field routes through escapeHtml(), numerics included," not
   "escape only the ones provably exploitable today").
   Every other `innerHTML`/`outerHTML`/`insertAdjacentHTML` sink in the file was checked
   and is already safe: KPI cards (868), Dead Code Register (888), PDT Ledger's other
   cells (931), Schema Drift (1055), Migration Impact trigger label (1076), Node Detail
   panel (1212-1238) — all route data through `escapeHtml()` or one of the file's other
   safe-output helpers (`fmt_usd`, `fmt_bytes`, `primaryChipHtml`, `evidenceListHtml`,
   `consumerListHtml`, `detailRow`). `el()`'s optional third `html` arg (line 540) is
   never called with a third argument anywhere in the file today — not an active sink,
   left as-is (would need its own escaping discipline if a future caller starts passing
   one).
4. **Guardrail test hardened** — `test_data_derived_fields_are_escaped_in_innerhtml_
   templates` (tests/test_l1_synthesis_outputs.py) previously only matched literal
   `${r.field}` / `${c.field}` tokens, so it was structurally blind to interpolation
   through an intermediate variable (`${label}`) or a map-callback parameter (`${e}`,
   `${v}`) — exactly the class of the three fixes above. Replaced with a real (if
   heuristic) allowlist-based JS-template safety checker: extracts every `${...}`
   placeholder reaching an innerHTML-class sink (including ones nested inside a
   `.map()` callback's own template literal), and requires each to be provably safe —
   wrapped in `escapeHtml()`/a known-safe helper, a numeric/`.length`/`.toLocaleString()`
   expression, a ternary/`||`/`+`/`-` of safe parts, or a `.map(fn).join(literal)` chain
   whose callback body is itself safe. Bare local variables are resolved against a
   safe-var set inferred from their own `const`/`let` assignment — **scoped per
   top-level IIFE/function block**, not file-global, because this file has two unrelated
   locals both named `label` (one in `evidenceHtml()`, escapeHtml-derived; one in the
   roadmap IIFE, raw-fallback-derived) — a flat global safe-var set would have let the
   first one's safety leak into the second and silently defeated the whole check. This
   was caught DURING test-writing (not by CI), via manual mutation testing against the
   real file.
5. **CI JS syntax check added** — new `scripts/check_dashboard_js_syntax.py`: builds a
   dashboard from the `enterprise_mono` fixture (same fixtures the Python suite uses),
   extracts every `<script>` block, and runs each through `node --check` in a temp file.
   Wired into `.github/workflows/strata-ci.yml` as a step right after `Run tests`, with
   `actions/setup-node@v4` added alongside the existing `setup-python`. Skips (exit 0,
   stderr note) if `node` isn't on `PATH` rather than failing the job outright. This is
   the same class of check round-1's handoff (now archived) describes doing manually/
   ad-hoc each round (`new Function(src)` in Node) — now a standing CI gate instead of a
   per-round manual step.

**What was verified:**
- Full suite: **132 passed** (same count as before — the guardrail test was rewritten in
  place, not added alongside a new one).
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files, no issues — this command's
  scope doesn't cover `tests/`/`scripts/`, matching CI exactly).
- **Negative control (mandatory per issue #29 item 4):** four separate mutation runs,
  each reverting one of this branch's `escapeHtml()`/`.map()` fixes and re-running the
  guardrail test — all four went RED with a specific, correct offender reported, then
  were restored and the suite went green again:
  1. Reverted PDT Ledger `${escapeHtml(e)}` → `${e}`: test failed, reported
     `explores || '<span...>none</span>'` as the offending expression.
  2. Reverted Migration Impact `views` `${escapeHtml(v)}` → `${v}`: test failed,
     reported the bare `v` placeholder and the enclosing `.map(...).join('')` chain.
  3. Reverted roadmap `${escapeHtml(label)}` → `${label}`: test failed, reported `label`.
  4. Reverted roadmap `${escapeHtml(cls)}` → `${cls}`: test failed, reported `cls`.
- **CI JS-syntax-check negative control:** temporarily broke `escapeHtml`'s own syntax
  (`function escapeHtml(s) { if (`) — `scripts/check_dashboard_js_syntax.py` correctly
  exited 1 with a Node `SyntaxError` pointing at the injected block; restored, script
  passed again (5/5 blocks).
- `scripts/check_dashboard_js_syntax.py` run standalone against the real (fixed) branch:
  5/5 generated `<script>` blocks pass `node --check`.

**Exact Next Steps (Round 1, superseded by Round 2 below):**
1. ~~Open the PR (`Closes #29`)~~ — done, PR #30.
2. ~~Pre-gate ritual before pushing~~ — done.
3. No version bump / tag needed — generator + test + CI-only change, no release
   artifact touched. (Still true in Round 2.)
4. No follow-up slice implied by this branch. (Still true in Round 2.)

### Round 2 — PR #30 gate findings (Codex + Artemis), commit `61701a9`

**What changed** (all in `src/strata/outputs/dashboard.py` and
`tests/test_l1_synthesis_outputs.py` unless noted):

1. **Codex P1 — handoff anchor placeholder.** This block's `Commit:` field said
   "set once the PR is opened" instead of a real 7-char SHA even after the PR was open.
   Fixed: anchored to `61701a9` (the Round 2 implementation commit) above, with the
   post-squash resolution path kept as a note, not a substitute for a real anchor now.
2. **Codex P2 — `uniqueAnchor` on the safe-wrapper allowlist.** `uniqueAnchor(base)`
   returns `base` verbatim, unescaped — it's a DOM-id-collision disambiguator, not an
   escaping helper, so treating it as a safe wrapper in the guardrail's allowlist was
   wrong even though no template currently interpolates its result directly (both call
   sites — `roadmapId`, `driftAnchor` — only feed it to `primaryChipHtml()`, which
   escapes it, or a non-sink `.id =` assignment). Removed from `_SAFE_WRAPPERS`.
3. **Artemis should_fix — guardrail sink-shape coverage.** The guardrail only matched
   `.innerHTML =`/`.outerHTML =`/`.insertAdjacentHTML(...)` followed immediately by a
   template literal. Extended to also match `+=` on both properties, and to resolve a
   bare identifier assigned to a sink (`el.innerHTML = x;`) back to its own
   `const x = \`template\`;` declaration in the same top-level scope — flagging it as
   unresolved/unprovable if no such declaration exists, per the file's existing
   allowlist-of-safe-shapes philosophy.
4. **`el()`'s dead third `html` parameter removed.** It was the one bare-identifier-
   into-innerHTML shape already in the file with no resolvable declaration (a plain
   function parameter) — grep confirmed no caller ever passes a third argument, so
   rather than special-case unreachable dead code in the guardrail, deleted the
   parameter and its `e.innerHTML = html` branch.

**What was verified:**
- Full suite: **132 passed**.
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files).
- `scripts/check_dashboard_js_syntax.py`: 5/5 generated `<script>` blocks pass
  `node --check`.
- **Negative control (mandatory, one per newly-covered shape) — each mutation applied
  to the real roadmap-row template in `dashboard.py`, guardrail run, reverted:**
  1. Added `${uniqueAnchor(r.action)}` as a direct interpolation → guardrail correctly
     went RED, reporting `uniqueAnchor(r.action)` as the offending expression.
  2. Added `li.innerHTML += \`${r.action}\`;` → RED, reported `r.action`.
  3. Added `const mutationHtml = \`${r.action}\`; li.innerHTML = mutationHtml;` → RED,
     resolved through the new template-var lookup and reported `r.action`.
  4. Added `li.innerHTML = someUnresolvedMutationVar;` (no matching declaration) → RED,
     reported `unresolved variable \`someUnresolvedMutationVar\` assigned to sink`.
  All four restored; suite green again after each.

**Known, intentionally out-of-scope gap:** `panel.innerHTML = rows.join('');` (node
detail panel) is a sink assignment the guardrail still does not trace — `rows` is built
via repeated `.push(...)` calls (each pushing the result of a safe wrapper:
`detailRow`/`statusBadge`/`consumerListHtml`), not a single provably-safe RHS expression
the existing `_is_safe_expr` machinery can evaluate. Manually verified safe (every
pushed value already routes through a safe wrapper). Tracing multi-statement array-push
accumulation was not part of the three sink shapes named in the Artemis finding and
would be a meaningfully larger change (push-site tracking, not sink-site tracking) —
left as a follow-up if a future review wants it, not silently declared "covered."

### Round 3 — PR #30 round-2 gate findings (Codex), commit set below

**What changed:**

1. **Codex P1 — invalid `Conductor Mode: none`.** `none` isn't a value in
   `conductor/CONDUCTOR_MODES.md`'s vocabulary (`patch | slice | full | audit`). Reclassified
   this whole branch as `patch` mode (matches its own "bug fix, one-file change" definition)
   in the block header above; kept the honest "no `standard.json`" detail as context, not a
   substitute for a real mode.
2. **Codex P2 — `detailRow` wrongly in `_SAFE_WRAPPERS`.** Audited every one of the (then
   nine) allowlisted helpers against its real `dashboard.py` implementation, one by one:
   `escapeHtml`, `fmt_usd`, `fmt_bytes`, `primaryChipHtml`, `evidenceListHtml`,
   `consumerListHtml`, `statusBadge`, `evidenceHtml` all escape/derive every data-derived
   value they interpolate from their OWN body — unconditionally safe regardless of what's
   passed in, so they stay in `_SAFE_WRAPPERS` (each one's reasoning is now a comment above
   the tuple in `tests/test_l1_synthesis_outputs.py`). `detailRow(key, valHtml)` is the one
   exception: it escapes `key` but returns `valHtml` **verbatim** — every real call site
   already escapes its second argument (confirmed by reading all 8 call sites), but the
   helper itself doesn't, so `${detailRow('X', r.name)}` would have passed the guardrail
   with a raw, unescaped second argument. Moved `detailRow` out of `_SAFE_WRAPPERS` into a
   new `_ARG_SAFE_WRAPPERS` tier: a call to one of these names is safe only when EVERY
   argument passed to it is itself provably safe (recursed via the checker's existing
   `_is_safe_expr` rules, using a new `_call_args()` helper to extract them) — not merely
   because the callee's name is on a list. (Considered making this generic to any function
   call, not just an explicit tier — rejected: e.g. `const d = evt.target.data();` is a
   zero-argument call whose result is raw untrusted data, not literal HTML built from its
   arguments; a name-scoped tier avoids misclassifying that shape as safe.)

**What was verified:**
- Full suite: **132 passed**.
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files).
- `scripts/check_dashboard_js_syntax.py`: 5/5 generated `<script>` blocks pass `node --check`.
- **Negative control (mandatory):** temporarily added `${detailRow('X', r.name)}` to the Dead
  Code Table's existing `tr.innerHTML` template (`r` already in scope there from the row's
  `.forEach(r => ...)` callback) — guardrail correctly went RED, reporting
  `detailRow('X', r.name)` as the offender. Reverted.
- **Positive control:** same spot with `${detailRow('X', escapeHtml(r.name))}` — guardrail
  correctly stayed GREEN (proves the new arg-recursion isn't overly strict). Reverted; `git
  diff src/strata/outputs/dashboard.py` confirmed empty before committing.

**Exact Next Steps (Round 3, superseded by Round 4 below):**
1. Push this branch; reply to both round-2 Codex inline threads (mode vocabulary,
   `detailRow` allowlist) describing the fix — replying is not resolving, resolution follows
   re-gate.
2. Re-run the gate on PR #30.
3. No version bump / tag needed.
4. No follow-up slice implied; the `rows.join('')` gap (Round 2, above) is still a candidate
   for a small follow-up if anyone wants the guardrail to trace array-accumulation sinks too,
   not a blocker for this PR.

### Round 4 — PR #30 round-3 gate finding (Codex), commit set below

**What changed** (`tests/test_l1_synthesis_outputs.py` only — no `dashboard.py` change was
needed; see verification below):

1. **Codex P1 — `.toLocaleString()` safe-ending trusted the wrong thing.** The guardrail's
   `_is_safe_expr` treated ANY expression ending in `.toLocaleString()` as safe, reasoning
   it only ever formats numbers. Wrong: `String.prototype.toLocaleString` exists too and
   returns the string UNCHANGED, so `${r.name.toLocaleString()}` (raw untrusted string,
   receiver never proven numeric) would have passed the checker unescaped — the same class
   of bug as Round 3's `detailRow` finding (trusting a method NAME instead of what it does
   with its receiver). Fixed: `.toLocaleString()` is now safe only when its receiver passes
   a new, narrower `_is_safe_numeric_expr` — numeric literal, `Number(...)`, `.length`,
   parenthesized/arithmetic (`+ - * /`) combinations of the same, or nothing else. This is
   deliberately NOT the same as `_is_safe_expr` ("won't inject HTML"): an already-escaped
   string is injection-safe but not numeric, and `'<img>'.toLocaleString() === '<img>'`
   proves generic safety isn't sufficient for this specific method ending.
2. **Audited every other method-based safe ending in the checker for the same mistrust
   shape** (per the finding's instruction to check `.toFixed()` and similar): the only
   other such ending is `.length` (line ~973), which is safe unconditionally — `.length` on
   a string/array is always a JS number by spec, no receiver-type ambiguity exists the way
   it does for `toLocaleString`/`toFixed`/`toPrecision`. `.toFixed()` does NOT appear
   anywhere in the checker's safe-endings list — the file's only two `.toFixed()` calls
   live inside `fmt_bytes`/`fmt_usd`'s own bodies (already unconditionally-safe entries in
   `_SAFE_WRAPPERS`, trusted as whole-function calls, not via a safe-ending regex), so
   there was nothing to change there.
3. **No real `dashboard.py` call site needed a change.** Audited all three real
   `.toLocaleString()` call sites (`total_queries||0`, `query_count||0`, `build_count||0`,
   all `<numeric-field>||0` shapes): none of them is ever the direct subject of a `${...}`
   interpolation inside an innerHTML-class sink template — the KPI-card one flows through
   `${escapeHtml(c.value)}` one level removed (already safe regardless of `c.value`'s
   content), and the two `detailRow(...)` ones build the node-detail-panel's `rows` array
   via `.push()`, which is the `rows.join('')` array-accumulation gap Round 2's handoff
   already documented as out of the guardrail's traced-sink scope. So tightening the
   safe-ending rule changed zero real templates — confirmed by the unmodified full suite
   passing and `git diff src/strata/outputs/dashboard.py` staying empty throughout.

**What was verified:**
- Full suite: **132 passed**.
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files).
- `scripts/check_dashboard_js_syntax.py`: 5/5 generated `<script>` blocks pass `node --check`.
- **Negative control (mandatory, exact shape from the finding):** temporarily changed the
  Dead Code Register's `source_file` cell from `${escapeHtml(r.source_file||'')}` to
  `${r.name.toLocaleString()}` (`r` already in scope from that row's `.forEach(r => ...)`)
  — guardrail correctly went RED, reporting `line 4843: r.name.toLocaleString()` as the
  offender. Reverted.
- **Positive control:** same spot with a numeric-literal receiver,
  `${(1234).toLocaleString()}` — guardrail correctly stayed GREEN (proves the new
  receiver-provability check isn't overly strict for the legitimate case). Reverted; `git
  diff src/strata/outputs/dashboard.py` confirmed empty before committing.

**Exact Next Steps (Round 4, superseded by Round 5 below):**
1. Push this branch; reply to the round-3 Codex inline thread (`.toLocaleString()`
   receiver-provability) describing the fix — replying is not resolving, resolution follows
   re-gate.
2. Re-run the gate on PR #30.
3. No version bump / tag needed.
4. No follow-up slice implied; the `rows.join('')` gap (Round 2) remains the one
   documented, intentionally out-of-scope tracing gap.

### Round 5 — PR #30 round-4 gate findings (Codex), commit 140f267 — FINAL checker-heuristic round

**What changed** (both `src/strata/outputs/dashboard.py` and
`tests/test_l1_synthesis_outputs.py`; commit 140f267):

1. **Codex — `fmt_bytes` was wrongly unconditionally-safe.** It sat in
   `_SAFE_WRAPPERS` alongside `fmt_usd`, but the two are NOT siblings the way the
   comment claimed. `fmt_usd`'s only body is `'$' + v.toFixed(2)` — `.toFixed`
   exists exclusively on `Number.prototype`, so any non-number argument makes
   `v.toFixed` `undefined` and calling it throws a `TypeError` before the `+`
   ever runs; there is no path back to input-derived text, so it legitimately
   stays unconditional (documented in a new, longer `_SAFE_WRAPPERS` comment).
   `fmt_bytes` is different: its four `b >= 1eN` threshold checks all evaluate
   to `false` for a non-numeric string (`>=` coerces via `ToNumber`, and every
   `NaN` comparison is `false`), so a string argument falls through every
   threshold to the final `return b + ' B'` — and for a string `b` that `+` is
   concatenation, not arithmetic, returning the input **verbatim** with `' B'`
   appended. `${fmt_bytes(r.name)}` would have passed the old allowlist
   unescaped. Moved `fmt_bytes` into `_ARG_SAFE_WRAPPERS` (same tier as
   `detailRow` — every argument must itself be independently proven safe).
2. **Codex — `.length` was trusted as an unconditionally-safe ending.** Every
   value this checker inspects is JSON-parsed record data, and a plain object
   can carry an own property literally named `length`
   (`r.length === '<img ...>'`) that shadows the real Array/String `.length`
   accessor entirely — `r.length` then returns that string, not a count. A
   genuine Array's or primitive String's `.length` IS always numeric (the JS
   engine won't let you assign it anything else), but the checker has no way to
   prove syntactically that a given receiver is actually one of those rather
   than a generic record. Dropped the unconditional `.length` trust from BOTH
   `_is_safe_expr` (the general HTML-safety prover) and `_is_safe_numeric_expr`
   (the narrower numeric prover round 3 introduced for `.toLocaleString()`
   receivers — it had the exact same blind spot, e.g.
   `r.length.toLocaleString()`).
3. **`Number` added to `_SAFE_WRAPPERS`** as the honest replacement for both of
   the above: `Number(x)` can only ever evaluate to a primitive number or
   `NaN` — there is no code path back to a string, so a template-literal
   coercion of its result is always digits/`NaN`/`Infinity`, never attacker
   text, regardless of what `x` is. This is the same "wrap it, don't
   special-case the checker" move the finding's brief required.
4. **Restructured every real `dashboard.py` call site** that needed it, in both
   directions — sink-scanned AND the `rows.join('')` sink the checker still
   can't trace (round 2's documented gap; fixing the *runtime* bug there too,
   since it's a real innerHTML sink even though the heuristic can't see it, not
   just a checker-satisfaction exercise):
   - `pdtCostSentence`'s `fmt_bytes(bytesProcessed || 0)` →
     `fmt_bytes(Number(bytesProcessed || 0))` (textContent-only sink, fixed for
     the underlying `fmt_bytes` correctness, not because the checker sees it).
   - PDT Ledger row: `fmt_bytes(r.bytes_processed)` →
     `fmt_bytes(Number(r.bytes_processed))` (real sink-scanned site).
   - Node-detail panel (`rows.join('')` sink): `fmt_bytes(d.bytes_processed||0)`
     → `fmt_bytes(Number(d.bytes_processed||0))`.
   - Cleanup Roadmap's `evCount` local: `(r.evidence_ids||[]).length` →
     `Number((r.evidence_ids||[]).length)` (this one WAS sink-scanned — `evCount`
     feeds `${evCount}` inside `li.innerHTML`, and `_safe_vars_for_scope` stopped
     trusting its assignment the moment the blanket `.length` rule was dropped;
     confirmed by rerunning the full suite, which would have gone RED here if
     left unwrapped).
   - Migration Impact accordion: both `(r.explores||[]).length` and
     `(r.fields||[]).length` occurrences used as direct interpolation values
     (not the ternary conditions — a ternary's condition branch is never
     rendered, so it doesn't need proving, and both leftover raw `.length`
     conditions were left untouched on purpose).
   - Node-detail panel's `views.length` → `Number(views.length)` (also a
     `rows.join('')`-sink site, same runtime-correctness reasoning as
     `d.bytes_processed` above).

**What was verified:**
- Full suite: **132 passed**.
- `ruff check src/ tests/ scripts/` and `ruff format --check src/ tests/ scripts/`: clean.
- `mypy src/strata --ignore-missing-imports`: clean (87 files).
- `scripts/check_dashboard_js_syntax.py`: 5/5 generated `<script>` blocks pass `node --check`.
- **Negative controls (mandatory, exact shapes from the finding), checked by calling the
  checker's prover functions directly (`_is_safe_expr`/`_is_safe_numeric_expr` imported from
  the test module) rather than mutating and reverting dashboard.py, since neither shape has a
  real call site to temporarily mutate:**
  - `fmt_bytes(r.name)` → `_is_safe_expr(...)` returns `False` (RED), correctly caught by the
    new `_ARG_SAFE_WRAPPERS` entry.
  - `r.length` → both `_is_safe_expr(...)` and `_is_safe_numeric_expr(...)` return `False`
    (RED) now that the blanket `.length` trust is gone from both provers.
- **Positive controls**, same direct-call method, confirming the real fixed patterns stay
  GREEN: `fmt_bytes(Number(r.bytes_processed))`, `fmt_usd(r.estimated_cost_usd)` (unchanged,
  still unconditional), `Number((r.explores||[]).length)`,
  `Number((r.fields||[]).length)-8` (the arithmetic residual after wrapping the base),
  `Number(views.length)` — all `True`.
- The full-fixture sweep test (`test_data_derived_fields_are_escaped_in_innerhtml_templates`,
  which runs the checker end-to-end against the real generated enterprise_mono HTML, not just
  synthetic expressions) passed both before AND after every dashboard.py wrap, confirming the
  `evCount`/`explores`/`fields` real sites needed the fix (they'd have gone RED without the
  `Number(...)` wrap once the blanket `.length` rule was removed) and that nothing else broke.

**Exact Next Steps:**
1. Push this branch; reply to all three round-4 Codex inline threads (`fmt_bytes`
   allowlist, `.length` safe-ending, handoff anchor) describing the fixes — replying is not
   resolving, resolution follows re-gate.
2. Re-run the gate on PR #30. Per the task brief, this is the FINAL round for
   checker-heuristic findings — if Codex round 5 raises a NEW heuristic gap, treat it as
   requiring a written justification for why the class of bug (`_SAFE_WRAPPERS` trusting a
   name instead of a body, or a safe-ending regex trusting a syntax shape instead of a
   receiver type) wasn't fully closed by rounds 2-5, rather than another one-off patch.
3. No version bump / tag needed.
4. No follow-up slice implied; the `rows.join('')` array-accumulation sink-tracing gap
   (documented since Round 2) remains the one intentionally out-of-scope item — this round
   fixed the two REAL vulnerabilities that happened to live behind it (`d.bytes_processed`,
   `views.length`) without closing the general tracing gap itself.

## 2026-08-18 — feat/dashboard-evidence-trust-core

Commit: 5cc13b9 (pre-merge branch anchor — implementation commit; squash-merge repo,
  post-squash resolve via `gh pr view 28 --json mergeCommit -q .mergeCommit.oid`)
Anchor semantics (squash-aware, per the convention slice-06 established): PRE-merge, the
  final commit on the PR branch is the implementation anchor. POST-squash, resolve the
  landed anchor deterministically via `gh pr view <PR#> --json mergeCommit -q
  .mergeCommit.oid` and use THAT for any HEAD check — no branch-SHA ancestry check is
  valid after a squash by construction.
Conductor Mode: slice (governing spec: conductor/slice-08-evidence-trust-core.md)
Context Budget: medium
Context Loaded: AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/index.md,
  conductor/README.md, active slice conductor/slice-08-evidence-trust-core.md,
  conductor/dashboard-north-star.md, conductor/slice-07-dashboard-ux.md (consumer-map
  split amendment), handoff-log latest block (slice-07), src/strata/outputs/dashboard.py,
  src/strata/l1/enrich.py, src/strata/l1/schema.py (schema_tables L1 fact + missing_table
  drift's `physical_table:` evidence id), src/strata/l1/types.py,
  src/strata/outputs/artifacts.py (`_cleanup_roadmap()` — evidence_ids[0] convention),
  src/strata/outputs/AGENTS.md (outputs serialize, they do not derive), tests/
  test_l1_synthesis_outputs.py, tests/test_schema_drift.py (missing_table fixture),
  output/enterprise_mono/*.json (real fixture artifacts).
Context Skipped: handoff-archive.md, mcp/ and cli/ (out of scope — no CLI wiring changed),
  docs/assets screenshots (out of scope).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump this slice — pure dashboard-generator addition, no release
  trigger.

### Round 1 — slice-08 initial implementation

1. **L1 facts inlined** — `_build_l1_facts(graph)` extends the data block with a new
   `L1_FACTS` constant: `usage` (per-explore query_count + content-reference count),
   `pdt_build` (build_count/bytes_processed/estimated_cost_usd per PDT view),
   `schema_table` (known column count per table, sourced from `l1.schema_tables`), plus
   the `period` dict.
2. **Evidence sentences** — `evidenceSentence(evId)` JS dispatcher switches on the id's
   namespace and composes an analyst-language sentence per the north star's example
   wording. Clicking ANY evidence chip toggles an inline `.evidence-sentence` panel;
   graph-resolvable chips also fire `focusGraphNode()`.
3. **URL-hash deep links** — Dead Code Register and PDT Ledger rows get stable DOM ids +
   copy-link buttons; `openHashTarget()` scrolls to and opens the target row's panel on
   load/hashchange.

**What was verified:** Full suite green (118 passed), ruff + mypy clean, self-contained
  HTML invariant held. **Browser click-through (Koa head, real Chrome)** caught a
  page-fatal bug the Python suite structurally could not see: the generated `attrEscape`
  helper shipped `/["\]/g` — a non-raw Python string collapsed a backslash layer, so the
  regex character class never closed, killing every script on page load. Fixed by
  eliminating the regex entirely (plain `dataset.evId` string equality). Added the
  pre-push parse guard for this class: extract each `<script>` block and `new Function
  (src)` it in Node.

### Round 2 — Codex round 2 (PR #28, 3 findings) fixed

1. **Output-encoding hardening** — the evidence-sentence panel was built via innerHTML
   over fixture-supplied fields. Fixed by construction: `toggleEvidencePanel` assigns
   `panel.textContent = evId + ': ' + evidenceSentence(evId)` — no HTML parsing of the
   sentence, ever. The now-redundant `escapeHtml(...)` calls inside the sentence-building
   helpers were removed (textContent would have double-escaped, e.g. rendering `&amp;`
   literally).
2. **Every-row copy-link/deep-link** — Schema Drift and Cleanup Roadmap rows had no row id
   or copy-link. `primaryChipHtml()` gained an optional `rowId` param so the DOM-anchor/
   copy-link target can diverge from the chip's evidence-sentence id: Schema Drift uses
   `tr.id = r.id` (the row's own unique `SchemaDriftRecord.id`); Cleanup Roadmap used
   `li.id = r.evidence_ids[0]` at this point (superseded in round 3 — see below).
3. **`schema_table:` sentence names columns, not just a count** — `_build_l1_facts` inlined
   `columns` alongside `column_count`; the JS case rendered names, capped at 30 with a
   `(+K more)` suffix (the cap itself was removed in round 3).

**What was verified:** Full suite green (121 passed — 3 new). ruff + mypy clean.
  **Round-2 browser re-verify (Koa head, real Chrome)** caught a second defect the 121
  Python tests could not: roadmap `li.id = evidence_ids[0]` DUPLICATED PDT Ledger row ids
  for both fixture zombies (invalid document; `getElementById` made the roadmap anchor
  unreachable). Interim fix at the time: claim the id only if not already taken
  (`if (!document.getElementById(primaryId)) li.id = primaryId;`) — the round-3 "defer-if-
  taken" rule, since superseded (see below).

### Round 3 — Codex round 3 (PR #28, 5 findings) fixed — this session

1. **`physical_table:` evidence namespace unhandled** — `missing_table` schema-drift
   records cite the physical table's own graph-node id (`physical_table:<name>`,
   `schema.py`'s `_schema_drift()`) as `evidence_ids[0]`; the Cleanup Roadmap uses
   `evidence_ids[0]` as its primary chip, so this fell through to the generic
   "no evidence sentence defined" fallback. Added a `physical_table` case to
   `evidenceSentence()`: resolves against `L1_FACTS.schema_table` — absent from schema
   facts states so plainly ("...is not present in the provided schema facts (scanned N
   tables)"); present reports column count + `source_file` from the graph node.
   `KNOWN_EVIDENCE_NAMESPACES` extended; the enterprise_mono fixture doesn't itself
   exercise a `missing_table` record, so the new pinned test uses the dedicated
   `tests/fixtures/schema_facts_drift.json` fixture (same one `test_schema_drift.py`
   already relies on for this scenario).
2. **Roadmap rows need row-unique DOM anchors** — replaced round 2's "defer-if-taken"
   rule (which made a claimed roadmap row's anchor silently unreachable) with a dedicated
   `'roadmap:' + primaryId` DOM-fragment namespace, `:2`/`:3`-suffixed on intra-roadmap
   collisions (multiple actions on one target). This is a DOM-anchor namespace only —
   evidence ids on chips stay verbatim (`primaryChipHtml(primaryId, r.target,
   roadmapId)`); `data-copy-hash` is the li's own unique id. `openHashTarget()` needed no
   change (`getElementById` resolves any id; the existing chip-fallback already covers a
   `tr.id`/`data-ev-id` divergence, same pattern as Schema Drift). The round-3-era defer
   rule is now dead code and removed — `roadmap:`-prefixed ids can never collide with a
   ledger/register/drift row's own id by construction.
3. **Dropped the 30-column display cap** in the `schema_table:` sentence — a wide table's
   sentence gets long, which is truthful and acceptable in a text panel; the cap was
   hiding exactly the fact a reader needs (whether the missing column is among the hidden
   ones).
4. **Handoff anchor consolidated** (this file) — the round-1/round-2 anchorless blocks
   folded into this single dated block with one `Commit:` line.
5. **Evidence aggregation moved into L1** — `content_reference_count`-per-explore and the
   schema-table column-count/columns derivation were computed directly in
   `_build_l1_facts()` (an outputs-layer function), violating `outputs/AGENTS.md`'s "outputs
   serialize, they do not derive." Moved into a new `evidence_facts(graph)` function in
   `src/strata/l1/enrich.py` (same seam style as `direct_view_consumers`/
   `view_consumer_map` — plain dict return, no graph mutation); `_build_l1_facts()` now
   only reshapes what that function returns into the evidence-id-keyed shape the JS looks
   up.

**What was verified:**
- Full suite: **124 passed** (121 prior + 3 new: `test_physical_table_evidence_namespace_
  resolves_present_and_missing`, `test_roadmap_and_ledger_dom_ids_are_all_unique`,
  `test_evidence_facts_aggregates_content_refs_and_schema_columns`; two existing tests
  updated in place for the new roadmap-id scheme and the removed column cap).
- `ruff check` + `ruff format --check` clean; `mypy src` clean.
- Regenerated the enterprise_mono fixture dashboard (the CLI's local HTTP server bind
  fails in this sandbox with `PermissionError`, but the HTML write happens first, so the
  regenerated file is current) and ran the pre-push parse guard: extracted all 5
  `<script>` blocks and `new Function(src)`'d each in Node — all 5 parse clean.
- **Behaviorally verified in Node** (same pure-logic-extraction technique as prior
  sessions): `evidenceSentence('physical_table:definitely.not.a.real.table')` →
  *"physical table 'definitely.not.a.real.table' is not present in the provided schema
  facts (scanned 12 tables)."*; a present table reports column count + source_file.
  `schema_table:` sentence now renders the full 8-column list for a real fixture table
  with no truncation. Walked the real generated `ROADMAP` (27 items): all 27 get unique
  `roadmap:`-prefixed DOM ids, zero collisions against `PDT_LEDGER`/`DEAD_CODE`/
  `SCHEMA_DRIFT` row ids.
- Self-contained-HTML invariant re-checked against the regenerated dashboard: only the
  same pre-existing vendored-library license-header URLs, unchanged — zero external
  requests.
- Live-browser click-through of round 3's new sentences/anchors was NOT re-run this
  session (no browser-use permission available here — same gap prior rounds flagged);
  worth a human eyeball on the next browser pass.

### Round 4 — Codex round 4 (PR #28, 2 findings) fixed — this session

1. **Live usage window dropped on the provider path** — `strata dashboard --looker-url
   --days N` passes `days` to `LookerSystemActivityProvider`, but `UsageFacts.to_mapping()`
   never carried a `period`, so `build_graph_with_provider()` called `enrich_graph()` with
   none and the serialized L1 `period` was `{}` — live evidence sentences would have
   claimed an unknown window despite the provider querying a known N-day range. Added an
   optional `period()` hook: NOT part of the `UsageProvider` Protocol (fixture/replay
   providers don't know their own window and must stay conformant without it), duck-typed
   via `getattr(provider, "period", None)` in `UsageFacts.from_provider()`. Added
   `LookerSystemActivityProvider.period()` returning the same `{start, end, days}` shape
   the fixture path already uses (`l1/fixtures.py`'s `load_usage_facts()`) — `end` is
   `datetime.now(UTC)`, `start` is `end - timedelta(days=self.days)`, mirroring the
   `f"{self.days} days"` relative-to-now filter `run_inline_query()` already sends.
   Threaded `period=mapping.get("period")` through `build_graph_with_provider()` in
   `pipeline.py`. No new period schema — one shape, matching the existing L1 convention
   exactly.
2. **PDT evidence sentence claimed a fabricated `/mo` figure** — `pdt_builds()` filters to
   `self.days` and sums bytes with zero monthly normalization, but `pdtCostSentence()`
   (this PR's own new wording) said `$X/mo`. Per operator disposition: do NOT extrapolate
   to a synthetic monthly number (that fabricates a different figure than what was
   measured) — state the cost over its real window instead, reusing `periodPhrase()`
   (same function `exploreUsageSentence()` already uses, including its honest "an unknown
   window" fallback when period is absent). New wording: `"$X estimated over the last
   N-day window (start → end)"` (or `"...over an unknown window"` with no period). Only
   this PR's own new sentence changed — pre-existing `/mo` UI surfaces (PDT Ledger table's
   COST/MO column, roadmap savings line, node detail panel's "Cost / mo" row) are
   untouched; explicitly out of scope per disposition. **Follow-up candidate, not fixed
   here:** those pre-existing `/mo` surfaces may now read as inconsistent next to the new
   window-labeled evidence sentence — worth a human call on whether to unify their wording
   in a future slice.

**What was verified:**
- Full suite: **126 passed** (124 prior + 2 new: `test_looker_provider_period_
  propagates_actual_query_window` — pins a non-30 `days=45` value so a hardcoded default
  couldn't fake it passing, asserts `(end - start).days == days`; `test_pdt_cost_
  sentence_states_real_window_not_fabricated_monthly` — asserts the fixed source line is
  present and the old `/mo)` line is gone).
- `ruff check` + `ruff format --check` clean; `mypy src` clean.
- Regenerated the enterprise_mono fixture dashboard (same sandbox `PermissionError` on
  the HTTP server bind as round 3 — HTML write happens first, mtime confirmed current)
  and ran the pre-push parse guard: extracted all 5 `<script>` blocks and
  `new Function(src)`'d each in Node — all 5 parse clean.
- **Behaviorally verified in Node** (same pure-logic-extraction technique as prior
  rounds): extracted `periodPhrase()` + `pdtCostSentence()` from the regenerated HTML and
  ran them against a synthetic 45-day period → `"built 3 times, processing 500000B ·
  $12.34 estimated over the last 45-day window (2026-01-01 → 2026-02-15) · used by 2
  explores (1 dead) · exists in resolved IR at 'models/foo.view.lkml'."`; against an empty
  period → `"...estimated over an unknown window..."` (no fabricated number, no crash).
- Self-contained-HTML invariant re-checked against the regenerated dashboard: only the
  same pre-existing vendored-library license-header URLs, unchanged — zero external
  requests.
- Live-browser click-through was NOT re-run this session (no browser-use permission
  available here — same recurring headless-session gap prior rounds flagged).

- **Round 5 (Koa head, inline, commit cd109fc)** — Codex caught that a live never-queried
  explore emits NO System Activity row, so the usage-keyed comprehension dropped exactly
  the explores whose dead verdicts most need evidence (chips fell to the "no usage row"
  fallback, substantiating neither verdict condition). `_build_l1_facts` now backfills
  every explore node with a `no_usage_row: true` zero-usage entry (content-ref count
  retained); the sentence states the absence as the zero-usage fact. Pinned by
  `test_l1_facts_covers_explores_without_usage_rows` (127 total). Done inline: a bounded
  single-file fix mid-verification, cheaper than a fifth dispatch round-trip.

- **Round 6 (Koa head, inline, commit fc6936c)** — Codex: `json.dumps` leaves `<` intact, so
  a fixture value containing `</script>` would terminate the inline script element and
  hand the rest of the payload to the HTML parser as live markup (reaches the page via
  the raw `L1_FACTS` literal, upstream of the textContent panel hardening). Fix:
  `_embed_json` wraps every one of the 9 JSON embed sites, encoding `<` as `\u003c` —
  byte-identical after JS string parsing, a pure serialization change. Pinned by
  `test_embedded_json_cannot_break_out_of_script_block` (poisons `period.start` with a
  breakout payload and asserts no script block carries it raw; 128 total).

- **Round 7 (Koa head, inline, commit f94e811)** — Codex (P1, correctly): the r5 backfill
  lived in `_build_l1_facts()`, re-deriving facts in the outputs layer — the exact drift
  the `evidence_facts()` seam exists to prevent, reintroduced by my own inline fix. The
  per-explore usage evidence (row-backed and `no_usage_row` backfill alike) now comes
  entirely from `l1.enrich.evidence_facts()` as `explore_usage_evidence`; the dashboard
  reshape is verbatim (test-pinned at both the seam and the reshape; 128 total).

- **Round 8 (Koa head, commit 071fdf1)** — Apollo blocker, correct: CI runs BOTH `ruff check`
  and `ruff format --check`; my r5/r6 inline rounds only ran the former, so two files
  landed unformatted. Formatting applied; the full gate set (check + format --check +
  pytest 128 + mypy) is now green together. Lesson recorded here rather than as a new
  memory shape: run the gate set CI runs, not the subset you remember.
  (Artemis's companion finding — PDT window wording "still unaddressed" — is stale: the
  wording landed in 3987015 and reads `estimated over ${periodPhrase()}` at
  dashboard.py:626. Disputed with evidence on the PR, not silently ignored.)

- **Round 9 (Koa head, commit f8fa376)** — Codex: prototype-chain lookups. A table named
  `constructor`/`toString` resolved to an inherited Object.prototype member, so a MISSING
  table rendered as present with an undefined column count — evidence contradicting its own
  verdict. Fixed as a CLASS: Codex named two sites; all four L1 fact lookups now route
  through `ownFact()`, and `NODE_BY_ID` uses `Object.create(null)` so a `__proto__` key
  can't poison it on assignment either. Regression test asserts no raw bracket lookup into
  a JSON-parsed fact map survives (129 tests). Full gate set run this time — check, format,
  pytest, mypy, Node parse — per the r8 lesson.

- **Round 11 (Koa head, commit 05ccac8)** — Codex: copy-link/hash asymmetry. The writer emitted
  the raw row id; the reader applied `decodeURIComponent`, so an id containing a literal
  percent-escape (quoted physical table `foo%20bar`) decoded to `foo bar` and matched
  nothing. Writer now encodes; reader decodes then falls back to the raw hash so links
  copied from an earlier build still resolve. Regression test pins both directions (130).
  NOTE: the post-reboot scratchpad venv was gone, so the first gate attempt silently ran
  against a STALE generated artifact — rebuilt the venv and re-ran everything against the
  real regenerated file. Same greens-by-construction shape as r8, different instrument.

- **Round 12 (Koa head, commit 7f49274)** — Codex: duplicate DOM ids on schema-drift rows (two
  views in different files can share one SchemaDriftRecord id). SECOND appearance of this
  class after r3's roadmap collision, so fixed as one shared `uniqueAnchor()` helper both
  row classes route through, rather than a third bespoke rule; roadmap's private counter
  deleted. First occurrence keeps the bare id so already-shared links stay valid. Also
  rewrote the drift/roadmap id test: it pinned literal source lines, so a correct refactor
  failed it while the property still held — it now asserts the property (131 tests).

- **Round 13 (Koa head, commit 54d01ad)** — Codex P1: the governing slice document had gone stale
  against twelve rounds of review-driven scope change (still said dashboard.py-only + read-only
  `enrich.py`, still prohibited any new id scheme). Reconciled: the L1 write, the
  provider/looker/pipeline reach for the live usage window, and the DOM-anchor namespace are
  now stated as implemented, with the ORIGINAL text preserved alongside — the expansions were
  review-driven, not drift, and a future session should be able to see which is which. Evidence
  ids remain verbatim; only DOM anchors got a namespace.

- **Round 14 (Koa head, commit 5cc13b9) — found by internal sweep, not review.** Escaping was
  applied per-FIELD rather than per-SOURCE: `source_file` was escaped in the Schema Drift row
  and raw in the Dead Code Register row three functions away, plus `kind`, `static_reason`,
  `usage_reason`, `physical_table`, and the KPI card's label/value/sub. Now uniform — every
  record field routes through `escapeHtml()`, numerics included, because exempting them by
  name rebuilds the enumerate-the-bad-cases shape. Test asserts the property structurally, not
  a field list; mutation-verified, and it caught two sites the sweep itself missed (132 tests).

**Exact Next Steps:**
1. Push branch; let Codex re-review round 4's fixes.
2. Human/Koa-head browser click-through of the new PDT cost-sentence window wording (the
   recurring headless-session gap).
3. Consider (follow-up slice, not this PR): unify the pre-existing `/mo`-labeled UI
   surfaces (PDT Ledger COST/MO column, roadmap savings, node detail panel) with the new
   window-labeled evidence-sentence wording, now that both coexist on the page.
4. Resolve threads only after the head verifies; dispatched agents never resolve threads
   or merge (standing house rule).
5. No version bump / tag needed — generator-only addition, not a release artifact change.

## 2026-08-18 — fix/dashboard-ux

Commit: 771560e (pre-merge branch anchor; squash-merge repo — post-squash resolve via
  `gh pr view <PR#> --json mergeCommit -q .mergeCommit.oid`)
Anchor semantics (squash-aware, per the convention slice-06 established): PRE-merge,
  771560e is the implementation commit on the PR branch. POST-squash, resolve the
  landed anchor deterministically via `gh pr view <PR#> --json mergeCommit -q
  .mergeCommit.oid` and use THAT for any HEAD check — no branch-SHA ancestry check is
  valid after a squash by construction.
Conductor Mode: slice (governing spec: conductor/slice-07-dashboard-ux.md)
Context Budget: medium
Context Loaded: AGENTS.md, conductor/index.md, conductor/README.md, conductor/templates/CONDUCTOR_SLICE_TEMPLATE.md, handoff-log latest block (slice-06), src/strata/outputs/dashboard.py, src/strata/l1/enrich.py, src/strata/l1/types.py, src/strata/l1/schema.py, src/strata/ir/types.py, src/strata/ir/resolver.py (node/edge id conventions), tests/test_l1_synthesis_outputs.py, output/enterprise_mono/*.json (real fixture artifacts, used to ground the schema-drift dedup investigation).
Context Skipped: handoff-archive.md (not needed beyond the one slice-06 block moved into it), mcp/ and cli/ (out of scope per task), docs/assets screenshots (explicitly deferred to a later pass).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no version bump this slice — pure dashboard-generator fix, no release trigger.

**What changed:** five operator-confirmed UX findings from a hands-on 0.1.8 dashboard
walkthrough, all in `src/strata/outputs/dashboard.py`:

1. **Node detail panel** — PDT/explore/view/physical_table clicks now render every
   fact `_build_graph_data` sources Python-side (cost, build count, bytes scanned,
   dead-marked consumer lists, PDT dependencies, referencing views), replacing the old
   name/kind/source/"DEAD/ORPHAN: Yes" starved panel.
2. **Vocabulary** — a `Status` row replaces the flattened DEAD/ORPHAN flag: PDT →
   ZOMBIE (purple) / UNUSED (orange) / IN USE (green); explore → DEPRECATE/KEEP
   (unchanged); view → ORPHANED (gray) / ZOMBIE VIEW (purple, new third state,
   structurally referenced but every consumer dead) / ACTIVE (blue). Legend extended
   to teach the new zombie-view/in-use-PDT colors.
3. **Evidence links** — `resolveEvidenceNodeId()`/`evidenceHtml()` turn evidence ids
   that name a graph entity into pills that scroll+select+fit+`tap` the graph node
   (`dead:explore:MODEL.NAME` remaps to `explore:MODEL:NAME`); ids with no graph node
   (`usage:`, `pdt_build:`, `schema_table:`, `field:`) render as plain non-pill text.
   Dead Code Register and the new Roadmap `<details>` evidence expansion both route
   through the same helper.
4. **Graph layout** — taller canvas (640px), tuned dagre `rankSep`/`nodeSep`/`padding`,
   `min-zoomed-font-size`, `fit: true` for initial-render fit-with-padding, plus
   overlaid +/−/fit buttons.
5. **Schema Drift dedup** — checked the artifact structure first: rows that look
   byte-identical genuinely differ by `field` (multiple LookML fields referencing the
   same missing column). Surfaced a `Field` column instead of a fake dedup; the JS
   groups on the full row (field included) and only shows a `×N` count if rows are
   truly identical even then.

`src/strata/l1/enrich.py` was read but not changed — every new field is derivable from
data it already produces plus the graph's own edges, computed in one edge pass inside
`_build_graph_data` (the codebase's existing convention of a small local lookup helper
per module, e.g. `validation.py`'s own copy of `_explores_using_view`, rather than
importing a private cross-module function).

**What was verified:**
- Full suite: **112 passed** (109 existing + 3 new tests covering PDT ledger fields on
  both fixture zombies + a negative-control "used" PDT, status vocabulary per kind
  including the new zombie-view/orphan/active three-way split, and the schema-drift
  dedup arithmetic — visible-column grouping collapses fewer rows than raw count,
  full-row-including-field grouping equals raw count).
- `ruff format --check` + `ruff check` clean.
- Self-contained-HTML invariant re-verified against a regenerated enterprise_mono
  dashboard: the only `http(s)://` strings are pre-existing vendored-JS-library doc
  comments (cytoscape/dagre/chart.js), unchanged by this slice.
- Pre-PR gate (`koa review --branch`) run per the mandatory ritual — see PR body for
  the disposition.
- **Not verified**: an actual browser click-through. This dispatch runs headless; the
  `browser-use` MCP tool required an interactive permission grant that isn't available
  here, so it errored on first call. Static review of the JS + the Python-side data
  tests substitute. Flagged explicitly in the PR body as the one item still needing a
  human eyeball before this is fully closed out.

**Review rounds (PR #25):** r1 — inherited consumers (fixture: base_customer under
customer_extended) + ACTIVE badge to legend blue; r2 — the r1 propagation promoted from a
dashboard-local loop into L1 (fix-the-shape applied to the fix itself); r3 — doc alignment;
r4 — the unification split along the REAL seam: `view_consumer_map()` (ancestry-aware
reachability: orphan/zombie-view verdicts + the panel) vs `direct_view_consumers()` (the
PDT ledger — a child view's PDT is its own materialization, so inherited consumers must
never credit a parent's PDT), one shared direct core; r5 — physical-table panel counts
pdt→upstream references, mirroring strata_impact(); r6 — this record corrected to the
final architecture.
mypy caught a str→tuple rebind in CI (venv suites don't run mypy — CI does).

**Exact Next Steps:**
1. Operator (or a session with browser-tool permission) opens the regenerated
   enterprise_mono dashboard.html in a real browser and confirms: node-detail panel
   populates correctly per kind, evidence pills jump to the right graph node, zoom/fit
   buttons work, graph fills the taller canvas legibly, Schema Drift shows the Field
   column with the ×N count only where genuinely duplicated.
2. Twin gate (Artemis/Apollo, this session's pre-PR ritual) + Codex on the PR; merge on
   clean per standing order (dispatched agents never merge).
3. No version bump / tag needed — this is a generator-only fix, not a release artifact
   change. If a future slice wants to regenerate the README dashboard screenshots to
   reflect these UX changes, that's explicitly out of scope here per the task brief.

## 2026-08-17 — feat/mcp-2x-migration

Commit: 1740642 (pre-merge branch anchor; squash-merge repo — post-squash resolve via
  `gh pr view <PR#> --json mergeCommit -q .mergeCommit.oid`)
Anchor semantics (squash-aware — this repo squash-merges, so branch SHAs never survive
  the merge): PRE-merge, 1740642 is the implementation commit on the PR branch. POST-squash,
  resolve the landed anchor deterministically via
  `gh pr view 22 --json mergeCommit -q .mergeCommit.oid` and use THAT for any HEAD check —
  no branch-SHA ancestry check is valid after a squash by construction. Canonical convention
  decision tracked in the repo issue "handoff anchors vs squash-merge".
Conductor Mode: slice (governing spec: conductor/slice-06-mcp-2x-migration.md)
Context Budget: low
Context Loaded: AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/index.md, handoff-log latest block, src/strata/mcp/server.py, tests/test_mcp_server.py.
Context Skipped: handoff-archive.md, docs/ (untouched).
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: v0.1.8 tag is the post-merge publish trigger (operator/Koa on instruction).

**What changed:** migrated off the removed 1.x `mcp.server.fastmcp` API to mcp 2.x
(`mcp.server.mcpserver.MCPServer`), closing the follow-up named in the 0.1.7 handoff.

- `src/strata/mcp/server.py`: `FastMCP("strata")` + the `_mcp_server.version` workaround →
  `MCPServer("strata", version=_server_version())` — 2.x takes version as a first-class
  kwarg, so the #20 workaround retires cleanly. `@server.tool()` and `run(transport="stdio")`
  are API-compatible; no tool code changed.
- `pyproject.toml`: `mcp>=2,<3`. The upper bound STAYS as policy — an unbounded pin is what
  shipped a dead-on-arrival strata-mcp once (PR #18); lift `<3` only with a 3.x migration.
- `tests/test_mcp_server.py`: asserts the public `server.version` (2.x) instead of the 1.x
  private `_mcp_server.version`.
- Version triple-bumped 0.1.8 (pyproject, mcpb/manifest.json, mcpb shim pin) — tag guard
  verified consistent at 0.1.8.

**What was verified (fresh venv on mcp 2.x, resolver picked 2.0.0):**
- Full suite **108 passed**; ruff format+check clean.
- Live stdio handshake: `serverInfo {'name':'strata','version':'0.1.8'}`.
- Full MCP sequence (initialize → initialized → tools/list): **all 18 tools register**.
- API grounded by introspecting the installed 2.0.0 SDK (module layout, MCPServer init
  signature, tool/run signatures) — not from memory or docs.

**Exact Next Steps:**
1. Twin gate + Codex on the PR; operator/Koa merges on clean per standing order.
2. Tag `v0.1.8` post-merge; watch the release run (publish + .mcpb).
3. Post-publish: fresh-index smoke (install ==0.1.8, handshake reports 0.1.8, mcp
   resolves 2.x).

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
