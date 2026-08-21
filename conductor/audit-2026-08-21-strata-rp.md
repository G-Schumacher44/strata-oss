# Adversarial Audit — strata-oss + review-pantheon (2026-08-21)

Post-slice-08/09 audit of both repos: strata-oss @ `ebd83ea` (main == audit branch base),
review-pantheon @ `5c211e5` (main). Five parallel adversarial review passes (MCP surface,
dashboard/XSS, L1/pipeline correctness, review-pantheon action, docs-vs-reality), findings
below triaged and the high/medium items independently reproduced or code-verified before
inclusion. Scope was deliberately held to what each project promises — no generic-hardening
findings.

Baselines: strata suite 132 passed (after `git submodule update --init`); review-pantheon
suite 311 passed, 10 skipped.

**Reproduction status key:** `[R]` = reproduced end-to-end with a scratch repo/fixture,
`[C]` = code-path verified by direct reading, `[A]` = agent-verified, spot-checked.

---

## Headline

1. The recent hardening work **held**: no reachable XSS in the dashboard (script-breakout,
   prototype-safety, per-context escaping all verified), the chart-renderer path sandbox is
   correct, the MCP "17 read-only + 1 sandboxed" split is true, and review-pantheon's
   injection/fail-closed/secrets guarantees all survived adversarial reading.
2. The real exposure is in **L1 verdict correctness**, not security: three reproducible ways
   the dead-code register issues a false "safe to delete" for live, heavily-queried entities
   (S-H1..S-H3). For a governance tool whose worst failure mode is a wrong deletion verdict,
   these are the priority fixes.
3. Docs drift has re-accumulated since the slice-05 remediation, in exactly the places
   `test_docs_consistency.py` doesn't reach (subcommands, `docs/`, layer AGENTS.md files).

---

## strata-oss — HIGH

### S-H1 [R] Explores declared outside `.model.lkml` get model `""` — usage never joins; false dead verdicts
- `src/strata/ir/resolver.py:81-84` (model attribution), `:296` (fallback), join at `src/strata/l1/enrich.py:80`
- The standard Looker pattern of a model file `include:`-ing `explores/*.explore.lkml` files
  produces explores keyed `".orders"` while usage rows are keyed `"main.orders"`. The join
  always misses.
- Reproduced: `main.model.lkml` + `explores/orders.explore.lkml` + a usage fixture with 500
  queries → `dead:explore:.orders` ("no usage row present and no content references") AND
  `dead:view:orders`. A 500-query explore and its view reported deletable.

### S-H2 [R] Same-named explores in different models silently merge — second model's explore vanishes, survivor gets a false dead verdict
- `src/strata/ir/resolver.py:99-101` — declarations are keyed by bare name repo-wide; a
  second plain `explore: orders` in another model file is treated as a *refinement* of the first.
- Reproduced: `alpha.model.lkml` + `beta.model.lkml` each declaring `explore: orders`, all 900
  queries on `beta.orders` → only `explore:alpha:orders` exists; output is
  `dead:explore:alpha.orders` + `dead:view:orders`. `beta.orders` isn't even auditable.
- Looker scopes explores per model; the declaration key needs the model in it.

### S-H3 [C] Live Looker queries hard-capped at 5000 rows, no sort, no pagination — truncation becomes "zero usage"
- `src/strata/l1/looker.py:172` (`"limit": "5000"`, no `sorts`, no paging anywhere in the file),
  consumed at `enrich.py` where `item is None` ⇒ `zero_queries = True`.
- Any instance with >5000 rows in the window (explore_usage is ~per-query-run rows) returns an
  arbitrary subset; explores past the cap get no row and land in the dead-code register.
  Same cap silently truncates `content_usage` and `pdt_event_log` (missing PDTs →
  `missing_build_facts`, cost 0). This bites at exactly the org size the tool targets.
- The absence-vs-zero distinction already exists for content refs (None sentinel) and for the
  evidence *sentence* (`no_usage_row`) — but not for the dead *verdict*.

## strata-oss — MEDIUM

### S-M1 [C] "/mo" labels on per-window PDT cost — 5 remaining sinks
- `src/strata/outputs/dashboard.py:924, 926, 953, 988, 1222` — `estimated_cost_usd` is a sum
  over the queried window (`--days N`), but the ledger header, zombie/kill badges, chart axis,
  roadmap savings, and node-detail row all say "/mo". With `--days 90` the "monthly" figure is
  3× overstated. Slice-08 fixed exactly this in the evidence sentence
  (`periodPhrase()`, and the KPI card says `PDT Cost / {days}d`) — the other five sinks still fabricate.

### S-M2 [R] "Active Explores" KPI subtracts dead views+explores from the explore count
- `src/strata/outputs/dashboard.py:852-858` — `active = explore_count - DEAD_CODE.length`, but
  the register holds dead views too (the adjacent card even labels it "views + explores"), and
  `explore_count` is `len(explore_usage)` (usage *rows*), not the graph's explore count. On the
  shipped enterprise_mono fixture the card renders 23; the true active-explore count is 28. The
  sub-line "11 dead" under "Active Explores" implies 11 dead explores when 6 are.

### S-M3 [C] `pdt_builds()` counts every `pdt_event_log` row as a build
- `src/strata/l1/looker.py:305-337` — no `pdt_event_log.action` field selected or filtered;
  `build_count += 1` per row. Trigger-check/create/other lifecycle events inflate build counts
  (and accelerate the S-H3 truncation).

### S-M4 [C] Missing `explore_usage` key conflated with "all zero" — no None sentinel, unlike content refs
- `src/strata/l1/enrich.py:28` (`usage = explore_usage or []`), `l1/fixtures.py:41`
  (`data.get("explore_usage", [])`). A usage-facts file without the key (or with it typo'd)
  marks every non-content explore dead. `test_review_patch_guardrails` currently locks this in.

### S-M5 [C] Backticked / hyphenated-project tables in derived-table SQL produce no `pdt→upstream` edge
- `src/strata/ir/resolver.py:438-441` — `\b(?:from|join)\s+([A-Za-z_][\w.]+)` can't match
  `` FROM `acme-analytics.gold.orders` `` (backtick blocks the match; `-` not in class) — and
  backticks are mandatory in BQ for hyphenated projects. `strata_impact` on such a table reports
  no dependents (false "safe to drop"); `missing_table` drift never fires for it.
  `${other_view.SQL_TABLE_NAME}` references (PDT-on-PDT) are also missed.

### S-M6 [C] `strata_validation_scope` docstring promises keys the tool never returns
- `src/strata/mcp/server.py:131-133` advertises `impacted_views, impacted_explores,
  impacted_fields`; `validation.py:60-72` returns `{changed, explores, unmatched}`. The
  docstring is the contract the LLM client sees — an agent reading the advertised keys
  concludes "no impact" on a change with real blast radius.

### S-M7 [A] Escaping guardrail blind spot: `panel.innerHTML = rows.join('')`
- `src/strata/outputs/dashboard.py:1237` vs the checker's three sink regexes
  (`tests/test_l1_synthesis_outputs.py:706-714`). The node-detail panel (14 `detailRow` values)
  has zero guardrail coverage; it is safe today only because each call site escapes manually.
  A future `detailRow('X', r.name)` ships unescaped with the guardrail green. Concatenation
  sinks (`'<b>' + x`) and identifier-arg `insertAdjacentHTML` are likewise unmatched shapes.

### S-M8 [A] README/docs drift (new since slice-05 remediation)
- `README.md:522` documents `strata conductor log-handoff` — command doesn't exist
  (conductor registers only `init`, `new-slice`, `status`).
- `README.md:121-166` "Try it now" never mentions `--recurse-submodules`; `thelook` and
  `gcs_analytics` are submodules, so two of the "three included playgrounds" arrive empty
  (also makes the test suite fail confusingly on a plain clone: KeyError deep in a fixture test).
- `src/strata/mcp/AGENTS.md` is stale on three counts: "Read-only tools only" (the exact claim
  slice-05 remediated in the README), "Vega-Lite via CDN" (JS is bundled locally — code is
  better than the doc), and a nonexistent `STRATA_TOOLKIT_PATH` env var (real ones:
  `STRATA_SKILLS_PATH`/`STRATA_CHARTS_PATH`).
- `README.md:460` + `docs/README.md:21` promise ADC coverage in `enterprise-deployment.md`;
  the doc has none.
- `.github/WORKFLOWS.md` lists deleted `sync-public.yml`, omits `review-gate.yml`/`setup-oss.yml`,
  and misdescribes `strata-pr.yml`'s trigger.
- `conductor/index.md:34` still says slice-08 is "review — PR open" (merged); served live to
  agents via `strata_conductor_status`.
- Seven docs cite governance authority file `intent.md`, which doesn't exist in the tree
  (GOVERNANCE.md, conductor/AGENTS.md, CONDUCTOR_MODES.md ×3, mcp/AGENTS.md, ir/AGENTS.md ×2,
  governance skill runbook).
- None of these are reachable by `test_docs_consistency.py` (it covers: README tool table,
  skill count, "N domain skills" phrases, top-level CLI table, 8 blocklisted phrases in 3 files).

## strata-oss — LOW

- **S-L1 [C]** `src/strata/viz/render.py:87` — chart spec embedded via bare `json.dumps` in a
  `<script>` block: a `</script>` in a title/data cell breaks out and runs arbitrary JS when the
  chart HTML is opened. dashboard.py fixed this class with `_embed_json` (9 sites); the chart
  renderer didn't get the same fix. (Low: requires attacker-influenced chart input + user opens
  the local file.)
- **S-L2 [A]** Schema-drift dedup key `[kind,table,column,field,file,reason].join('')`
  (dashboard.py:1033) is delimiter-less — `orders|id` vs `order|sid` collide and a real distinct
  drift row hides behind `×2`.
- **S-L3 [A]** Zombie PDTs render "Kill PDT / unused-pdt" in the roadmap
  (artifacts.py:61-71 buckets `zombie` under `review_unused_pdt_cost`) — vocabulary regression
  vs the zombie≠unused distinction the rest of the UI teaches.
- **S-L4 [A]** Per-part backticked `sql_table_name` (`` `proj`.`ds`.`t` ``) normalizes wrong
  (resolver.py:233 strips only outer backticks) → spurious `missing_table` drift.
- **S-L5 [A]** Column drift match is case-sensitive (schema.py:85); BQ columns resolve
  case-insensitively → false `missing_column`.
- **S-L6 [A]** Cost rate hardcoded `$5.0/TB` (looker.py:337); BQ on-demand is $6.25/TiB since
  mid-2023 (~27% understated). Labeled "estimated", so low.
- **S-L7 [A]** `*.dashboard.lookml` files are never parsed (parser.py rglob `*.lkml`), so
  in-repo dashboard references can't protect an explore (live content_usage partially covers).
- **S-L8 [A]** tests/scripts/docs inventories drifted: tests/README table missing
  `test_mcp_server.py`; "playgrounds are git submodules" (one is in-tree); scripts/README
  missing `benchmark_scenarios.py`; docs/README missing `benchmarks/gemma4_spec.md`.

## strata-oss — verified clean (attack surface that held)

- Dashboard escaping claim (ebd83ea) is truthful: every innerHTML/attribute interpolation
  escaped for its context; `_embed_json` neutralizes `</script>` and U+2028/9; deep-link
  encode/decode round-trips; `Object.create(null)` + `ownFact` prototype-safety is real.
- MCP surface: 18 tools = 17 pure reads + 1 writer; render_chart sandbox
  (`resolve()` + `is_relative_to` on `~/.strata/output` and `/tmp`) rejects traversal,
  absolute paths, and symlink escapes; no network/subprocess/eval on any tool path; skill
  lookup is basename-compared (no path traversal); truncation flags (find_field 50,
  navigate 5) boundary-correct; MCP 2.x migration verified against the installed 2.0.0 SDK
  (version reporting, error wrapping — a raising tool yields an error result, not a crash).
- L1 logic that held: zombie/unused/orphan distinctions (direct vs ancestry consumer maps),
  content-refs None sentinel, `missing_build_facts` honesty, Looker API errors raised not
  swallowed, extends cycles detected, refinement merge order.
- Security-hardening doc claims all match code (stdio-only, token file perms 0600 + checked
  on read, HTTPS enforced except localhost).
- Versions consistent at 0.1.8 everywhere; release.yml mechanically enforces the triple.

---

## review-pantheon

No high or medium findings. The stated guarantees were attacked and held:

- **Actions injection: clean.** No `${{ }}` in any `run:` block (guard script verified live);
  all untrusted values travel via `env:`; PR title/branch fenced with randomized markers;
  GITHUB_OUTPUT written via random-delimiter heredocs for every model-derived value (the
  `verdict\ncolor=green` smuggle is closed).
- **Gate is fail-closed at every layer.** Unknown/empty color → exit 1; missing/malformed
  verdict → UNVERIFIED; worst-wins ordering correct (red > unverified > yellow > green);
  decide steps emit outputs before failing so continue-on-error can't lose a red verdict;
  malformed state file aborts the CLI lane.
- **Verdict vocabulary correct** — no reject-word maps to a pass; blocker invariant is
  strict-bool and can only worsen a verdict.
- **Secrets: clean.** Tokens only via `with:`; renderer redacts credential values and
  token shapes on both parse and raw-fallback branches, before truncation.
- **Fork posture correct**: bare `pull_request` only (runtime-allowlisted;
  `pull_request_target` rejected), fork-no-secret → NOT-GATED skip distinguished from
  missing-secret failure.
- **claude-code-action SHA-pinned** at all five `uses:` sites with mechanical drift tests.
- strata-oss's `review-gate.yml` is byte-identical to the README Quick start as claimed, and
  its permissions (`contents: read`, `pull-requests: write`, `persist-credentials: false`)
  match the documented minimum exactly.

Lows:
- **RP-L1** Consumers (including strata-oss) install via mutable `@v1` while the action
  SHA-pins its own upstream. Disclosed in SECURITY.md's blast-radius section, so noted once,
  not inflated: the project's first external consumer took the mutable form; Way A pins a SHA.
- **RP-L2** Docs-only detection treats any `docs/**` path (e.g. `docs/deploy.sh`) as docs →
  Apollo skip. By design per DESIGN.md, Artemis still reviews; noted for completeness.
- **RP-L3** Stale references: `verdict.py:53-54` cites removed `action/decide_verdict.py`;
  RELEASING.md says "all three jobs" (ci.yml has four); install.sh Way-A pin lags at v0.2.2
  (disclosed as discretionary policy).

---

## Suggested priority

1. **S-H1/S-H2** — resolver keying (model attribution + per-model declaration keys). Both are
   in the same few lines of `_collect_declarations`; both reproduce with 3-file repos, so they
   make good regression fixtures. Fixtures currently can't catch either (all fixture explores
   live in uniquely-named `.model.lkml` files).
2. **S-H3/S-M3/S-M4** — make the dead *verdict* honor absence-of-data the way the evidence
   sentence already does; select+filter `pdt_event_log.action`; either paginate or detect the
   5000-row cap and mark affected entities "usage unknown".
3. **S-M1/S-M2** — the two dashboard number/label bugs (visible to every user).
4. **S-M6, S-M8** — docstring contract + docs drift batch (mostly mechanical).
5. **S-L1** — port `_embed_json` to `viz/render.py` (small, closes the class).
