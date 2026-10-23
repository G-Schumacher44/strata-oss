# Handoff — refactor/import-strata-lookml

**Mode:** Patch (mechanical, repo-wide)
**Date:** 2026-10-23

## What changed
- `git mv src/strata src/strata_lookml`. The import package name `strata` collided with the
  unrelated PyPI project `strata` (26.0.0 ships `strata/__init__.py` and `strata/config.py`), so
  installing both in one environment overwrote files.
- Every importer rewritten: `from strata...`/`import strata...` in src, tests, scripts, mcpb shim;
  `-m strata.cli.main` subprocess calls in tests; the L0 offline-import subprocess probe in
  tests/test_security.py; `src/strata/...` paths in pyproject (wheel `packages`/`include`), CI
  (`mypy`, the L0 network-import grep), GOVERNANCE.md, AGENTS.md files, docs, README.
- `[project.scripts]` targets moved to `strata_lookml.*`. Console-script names `strata`,
  `strata-mcp`, `strata-chart` are unchanged.
- No `strata` compatibility shim package (it would recreate the collision).
- ruff re-wrapped three import lines that grew past the line limit. No behavior changes.
- One doc fix: the schema-refresh skill told users to run `python -m strata --help`, which never
  worked (no `__main__`). It now says `.venv/bin/strata --help`.

## Not changed on purpose
- The `client_guid=com.gsanalytics.strata.cli` OAuth identifier: an external registration string,
  not a module path.
- The MCP server name `strata`, the `.mcp.json` server key, and `~/.strata/` config paths.
- Historical conductor docs (handoff-log, handoff-archive, slice specs, templates) still say
  `src/strata`. They are records of past work.
- mcpb shim pin stays `strata-lookml==0.1.8`. Codex P2 on #45: importing `strata_lookml` directly
  would break the bundle against that pin. The shim now resolves the installed distribution's
  `strata-mcp` console-script entry point, so it works with both the 0.1.8 pin (`strata`) and the
  renamed package. Verified with an MCP stdio round-trip (18 tools) on both. The old direct import
  fails on the 0.1.8 pin with ModuleNotFoundError.

## Landing order
Merge this last, after the open src/strata PRs (#33, #35–#44). Each of them needs a rebase onto
this; git rename detection should carry their hunks across, except where they add new `from strata`
import lines (those need the same rewrite).

## Verification
- ruff check, ruff format --check, mypy src, pytest (132 passed): all green.
- Wheel: 0 entries under `strata/`, 166 under `strata_lookml/` (equal to the tracked file count),
  data dirs complete. Installed next to `strata==26.0.0` in a fresh venv: both import,
  `strata --help` / `strata-chart --help` exit 0, MCP stdio `initialize` + `tools/list` returns 18 tools.
- CI's L0 network-import grep now points at the real path. Before this it would have silently
  passed on a missing dir (`2>/dev/null`), so the path had to move with the package.

## Exact Next Steps
- Land the open fix PRs, rebase this, merge it last. Then `chore/release-0.1.9-readiness`
  (stacked), then the 0.1.9 version bump after #44.
