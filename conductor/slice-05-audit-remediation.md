# Slice 05: Audit remediation — truthful docs, real zombie flagging, serverInfo version

Date: 2026-08-17
Status: review
Phase: post-publish hardening
Depends: slice-04-pypi-packaging.md

```yaml
conductor_mode: slice
context_budget: medium
handoff_required: true
stable_tag_required: false
```

## Objective

A claim-by-claim docs-vs-code audit of the just-published `strata-lookml` package (PR #18)
found 12 non-confirmed findings plus two filed issues (#19 mirror residue, #20 serverInfo
version). The operator ordered all of them fixed in one PR before the 0.1.7 release. This
slice records that contract: one real code fix (zombie PDT flagging — the README's flagship
claim was not actually computed), one protocol-correctness fix (MCP serverInfo version),
eleven docs-truthfulness corrections, mirror-era file removal, and the 0.1.7 version bump.

## Scope

- **L1** (`src/strata/l1/enrich.py`): PDT ledger status enum gains a real `zombie` value,
  computed by reusing the existing dead-code register (no second deadness derivation).
- **Outputs** (`src/strata/outputs/dashboard.py`, `artifacts.py`, `mcp/tools.py`): wire the
  new status through the dashboard badge/graph/chart and the cleanup roadmap / usage summary
  consumers that read `pdt_ledger[].status`.
- **MCP** (`src/strata/mcp/server.py`): serverInfo reports the installed `strata-lookml`
  package version instead of the `mcp` SDK's version.
- **Governance/docs only**: README.md, docs/*.md, GOVERNANCE.md, AGENTS.md, scripts/README.md —
  no behavior change, truthfulness corrections against verified current-repo reality.
- **Packaging**: pyproject.toml, mcpb/manifest.json, mcpb/pyproject.toml version fields →
  0.1.7 (no tag pushed).
- **Removal**: mirror-era residue (`.publicignore`, `scripts/check_public_release.py` + its
  test) left inert after the sync-to-oss job was deleted in PR #18.

## Implementation Order

1. `l1/enrich.py`: derive `dead_explore_keys` from the already-computed dead-code register in
   `enrich_graph`; thread it into `_pdt_ledger`; add the `zombie` status branch (has build
   facts, has consumers, all consumers are dead explores).
2. `outputs/dashboard.py`: distinct zombie badge/color/legend entry (not the same visual as
   plain `unused`); `outputs/artifacts.py` cleanup roadmap and `mcp/tools.py` usage-summary
   pick up the new status.
3. `mcp/server.py`: resolve `strata-lookml`'s installed version via `importlib.metadata`,
   set it on the FastMCP server's underlying `Server.version` (no public constructor kwarg in
   FastMCP 1.29 — verified by reading the installed SDK source, not guessed).
4. Regression tests: enterprise_mono fixture zombie PDTs assert `status == "zombie"` +
   dashboard HTML flags them; negative control (a PDT with a live consumer stays non-zombie);
   serverInfo version test; extended docs-consistency test for "N domain skills" drift.
5. Docs corrections (README, docs/*, GOVERNANCE.md, AGENTS.md, scripts/README.md) per the
   audit's 11 numbered findings — each checked against current repo state before editing.
6. Remove mirror residue (`.publicignore`, `scripts/check_public_release.py`, its test,
   `scripts/README.md` row) — Closes #19.
7. Version bump to 0.1.7 in all three pinned locations; run `release.yml`'s tag-match guard
   logic locally against "0.1.7" (positive) and a mismatched tag (negative control).

## The Hard Constraint

The zombie-PDT status must be derived from the **same** dead-code register the dashboard
already trusts — not a second independent "is this explore dead" check. Two sources of truth
for the same fact is exactly the class of bug this audit exists to prevent.

## Acceptance Criteria

- [x] `pdt_attribution_full_funnel` and `pdt_customer_value_score` (enterprise_mono fixture)
      report `status == "zombie"`, distinct from `unused`
- [x] Dashboard HTML renders a distinct zombie flag for those two PDTs (not the plain
      "In Use" green badge the audit caught)
- [x] A PDT with a live consumer does not get flagged zombie (negative control)
- [x] MCP `serverInfo.version` reports the installed package version, never the `mcp` SDK's
- [x] All 12 audit doc findings + 2 issues (#19, #20) addressed
- [x] `pyproject.toml` / `mcpb/manifest.json` / `mcpb/pyproject.toml` all read `0.1.7`;
      release.yml's verify-tag-matches-versions logic passes locally against "0.1.7"
- [x] `.venv/bin/pytest` — full suite green (count change from removed/added tests noted)
- [x] `ruff check` + `ruff format --check` clean
- [x] `conductor/handoff-log.md` — entry with Commit: hash
