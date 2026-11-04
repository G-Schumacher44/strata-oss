# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-03 — chore/release-0.1.9 (version bump, stacked on #46)

Commit: de7af40 (#46 head this bump sits on; the bump itself is the next commit on this branch.
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
  Release -> `mcp-publisher login github && mcp-publisher publish` for the registry.

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
