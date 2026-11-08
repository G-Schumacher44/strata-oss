# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-08 — feat/s0-generated-reference (generated CLI/MCP reference + drift check, spec slice S0)

Commit: ac022ce
  (Implementation commit; the PR squash-merges.)
Post-merge: resolve the landed anchor with `gh pr view <PR> --json mergeCommit`.
Conductor Mode: patch — docs/tests/scripts only; no runtime behaviour change.
Context Budget: low
Context Loaded: ux-agentic-cli-docs-spec-2026-11-08 (§1, D1/N4/N5, D14, S0), tests/test_docs_consistency.py, mcp/server.py, cli/main.py.
Exact Next Steps: operator reviews/merges; then S1 (spec) — D10 hides `lint`, which the generator and the N5 hidden-command filter already handle (rerun `python scripts/gen_reference.py` in that PR).

### What changed

- `scripts/gen_reference.py [--check]` writes `docs/reference.md` from the real click root group (every non-hidden command/subcommand: usage, options with envvars/defaults, first docstring paragraph) and the server's real `list_tools()` on an empty graph (name, title, description, parameters, annotations), plus derived counts. Deterministic: sorted, no timestamps, home dir rendered as `~`.
- `tests/test_docs_consistency.py`: `test_reference_is_current` (committed == generated), `test_readme_counts_match_introspection` (every `N tools` / `N analysis tools` / `N read-only` phrase), and the README CLI-table test now ignores hidden commands (N5). pytest already covers the check, so no separate CI step.
- `docs/cli-guide.md` summary table and the `mcp/AGENTS.md` signature list replaced with links to the reference (N4 drift removed).

### Gates

ruff check + format --check clean, mypy clean, pytest 219 passed. Negative control: editing the `auth logout` help string without regenerating fails `test_reference_is_current` and `gen_reference.py --check` (exit 1); regenerating passes; mutation reverted.
