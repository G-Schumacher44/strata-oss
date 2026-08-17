# Slice 04: PyPI packaging as strata-lookml (trusted publishing + .mcpb + install docs)

Date: 2026-08-16
Status: review
Phase: distribution
Depends: none

```yaml
conductor_mode: slice
context_budget: medium
handoff_required: true
stable_tag_required: false
```

## Objective

Give Strata a real distribution surface. The repo has been public since 2026-07-12 with no
PyPI package and no registry presence — installable only by cloning. This slice packages the
distribution as **`strata-lookml`** (the names `strata` and `strata-mcp` are taken on PyPI by
unrelated projects; "Strata" remains the product name and the console scripts are unchanged),
wires tokenless PyPI publishing into the existing tag-driven release flow, ships a Claude
Desktop `.mcpb` bundle per release, and documents modern install paths (`uvx`/`pipx`,
Cursor/VS Code one-click).

Authored retroactively at the review gate's direction (PR #18 Codex P1: spec-before-build):
the implementation was dispatched from an out-of-repo research contract; this document is the
in-repo record of that contract so the acceptance gates live where the workflow expects them.

## Scope

Packaging metadata, CI release workflow, new stand-alone `mcpb/` bundle dir, README, and one
line of CLI metadata (`click.version_option` package name). **No behavior changes under
`src/` beyond that metadata line.** Layers: Governance/tooling only — no L0 IR, MCP tool, L1,
or L2 logic touched.

## Implementation Order

1. `pyproject.toml`: `name = "strata-lookml"`, version `0.1.6`; console scripts unchanged.
2. `src/strata/cli/main.py`: `click.version_option(package_name="strata-lookml")` — Click
   resolves the installed distribution's metadata by this exact name; leaving `"strata"`
   makes `strata --version` raise after the rename.
3. `release.yml`: `publish-pypi` job — OIDC trusted publishing via
   `pypa/gh-action-pypi-publish@release/v1`, `permissions: id-token: write`, artifact
   handoff from the existing build job, no stored token.
4. `.mcpb` bundle: `mcpb/` dir (manifest `server.type: uv` + shim entry point, since the
   spec has no published-package mode) + `mcpb validate`/`mcpb pack` step attaching the
   bundle to the GitHub Release.
5. README: Installation section (`uvx --from strata-lookml strata-mcp` — a bare
   `uvx strata-lookml` fails, no script matches the distribution name), Cursor/VS Code
   deeplink badges, naming-split note.

## The Hard Constraint

**No step may green without producing a working artifact.** The publish job must fail closed
until the operator configures the PyPI Trusted Publisher (project `strata-lookml`, repo
`strata-oss`, workflow `release.yml`, environment `pypi`) — that failure is documented as
expected, never patched around with a stored token.

## Acceptance Criteria

- [x] `python -m build` produces sdist + wheel; wheel installs into a fresh venv and all
      three console scripts (`strata`, `strata-mcp`, `strata-chart`) resolve
- [x] `strata --version` reports 0.1.6 from the installed `strata-lookml` metadata
- [x] Full test suite green; `ruff check` clean on touched Python
- [ ] First `v0.1.6` tag push publishes to PyPI and attaches `strata-lookml.mcpb` to the
      Release (end-to-end proof — requires the operator's Trusted Publisher config first)
- [ ] `uvx --from strata-lookml strata-mcp` verified against a real MCP client post-publish
