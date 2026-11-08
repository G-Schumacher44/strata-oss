# Handoff: fix/escaping-callback-scope

Commit: resolve the landed anchor with `gh pr view <PR> --json mergeCommit` (squash-merge).
Conductor Mode: patch — test-helper precision fix only; no src/ change, no version bump.

## Change

`tests/test_l1_synthesis_outputs.py` (escaping guardrail): `_safe_vars_for_scope` no longer adds
every `.forEach/.map((item, index) =>` index name to the block-wide `safe_vars`. The index is now
trusted per callback body: `_callback_index_scopes` records each callback's body span (line
comments blanked first so prose apostrophes don't derail the paren matcher), `_safe_vars_at` adds
the index only for sinks/placeholders positioned inside it (flattened nested placeholders now carry
their source offset via `_Placeholder`), and `_neutralize_maps_and_slices` trusts a `.map` callback's
2nd param only while checking that callback's body. Closes #31. The real dashboard output is
unchanged in outcome (`${i+1}` inside the roadmap `forEach` is still proven safe).

## Verification

- New tests: `test_guardrail_callback_index_is_scoped_to_its_callback` (the issue's example, plus the
  bare-identifier sink form) and `..._still_trusted_inside_its_callback` (forEach body, map body,
  and the item param still untrusted). Negative control: re-adding the block-wide index trust makes
  the scoped test fail; restored, both pass.
- ruff check/format, mypy src clean. Full pytest: 182 passed, 1 failed —
  `test_pdt_ledger_unused_status_unaffected_by_zombie_detection`, failing identically on untouched
  origin/main (pre-existing, unrelated). The real-dashboard guardrail test passes.
