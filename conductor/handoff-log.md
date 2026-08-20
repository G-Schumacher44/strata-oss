# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

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
