# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-08-19 — fix/dashboard-innerhtml-escaping-sweep

Commit: (pre-merge branch anchor — set once the PR is opened; squash-merge repo,
  post-squash resolve via `gh pr view <PR#> --json mergeCommit -q .mergeCommit.oid`)
Conductor Mode: none — this repo has no `conductor/standard.json` (Conductor-stamped
  governance script skipped per its own instructions); scope came directly from GitHub
  issue #29 (a post-merge Artemis audit of PR #28 / slice-08, commit 6c9eede).
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

**Exact Next Steps:**
1. Open the PR (`Closes #29`), including the sink-sweep list and negative-control
   evidence from this entry in the PR body.
2. Pre-gate ritual (`koa review --branch ... --base main`) before pushing, per the
   dispatch's mandatory pre-PR gate instructions.
3. No version bump / tag needed — generator + test + CI-only change, no release
   artifact touched.
4. No follow-up slice implied by this branch; issue #29's optional item 4 (CI JS parse
   step) is now done, not deferred.
