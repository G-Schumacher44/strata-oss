# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

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
