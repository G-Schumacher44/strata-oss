# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

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

Final tree (post-merge): see the PR comment trail for the verbatim lines.
