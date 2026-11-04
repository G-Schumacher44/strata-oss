# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## Date: 2026-11-04 — fix/security-0.1.9 (security hardening before the 0.1.9 tag)

Commit: 39be7b8 (the fix commit; the docs commit and any review fixes follow it. The PR squash-merges; post-merge resolve
  the landed anchor with `gh pr view <this PR> --json mergeCommit`.)
Conductor Mode: patch — security fixes from a read-only audit at origin/main 9d19e42, plus the
  docs that describe them. No new MCP tool, no layer-boundary change.
Context Budget: medium
Context Loaded: AGENTS.md, handoff-log, generate_schema.py + scripts/generate_schema_facts.py,
  l1/looker.py, cli/auth.py, cli/mcp.py, mcp/server.py + ir/store.py, viz/render.py,
  mcp/tools.py, cli/dashboard.py, ir/parser.py, SECURITY.md, docs/security-hardening.md,
  docs/enterprise-deployment.md, README security sections.
Grounding: Looker OAuth guide https://docs.cloud.google.com/looker/docs/api-cors (auth on the UI
  host with client_id/state/S256 challenge; JSON POST to /api/token on the API host; redirect
  URIs matched exactly; registration via Admin or register_oauth_client_app with group_id; no
  refresh request documented). bq `--parameter` ARRAY syntax and the identifier limitation:
  https://docs.cloud.google.com/bigquery/docs/parameterized-queries. `--max_rows` default 100 and
  `--maximum_bytes_billed`: https://docs.cloud.google.com/bigquery/docs/reference/bq-cli-reference.
Exact Next Steps: operator merges after twins pass -> tag v0.1.9 per the previous handoff (now in
  handoff-archive.md). First real Looker login is the live validation of the OAuth flow; until
  then the docs label it "not yet validated against a live instance".

### What changed

- generate-schema: one source for query construction (`build_columns_query`), shared by the CLI
  and the script; identifier allowlist; table names as `@names` ARRAY parameter; bytes/rows caps.
- Looker OAuth: new `l1/oauth.py` (PKCE, state, `code_from_callback`, `LoopbackReceiver`);
  `auth login` loses `--code`, gains `--api-url`, `--client-id` (alias `--client-guid`),
  `--timeout`; `--no-browser` = paste-on-stdin.
- Token: `LookerToken.ensure_usable_for` is the single origin+expiry check, run at runner
  construction and per request; redirects refused via a no-redirect opener; refresh token not
  stored; atomic 0600 write, 0700 dir; loose perms refused.
- D-1..D-4 local hardening (cache age, stdout in MCP, .html, 127.0.0.1 bind, symlink skip).

### Design calls (conservative options taken)

- Fixed loopback port 48765, not ephemeral: Looker matches registered redirect URIs exactly.
  BREAKING for anyone who registered the old 8765 URI; CHANGELOG says so.
- Refresh token dropped rather than stored unused (no documented refresh grant).
- Token directory: create missing dirs 0700 and keep `~/.strata` 0700, but never chmod any other
  existing directory — a custom `--token-path` in a group/other-accessible directory is refused,
  checked before the browser opens (a code is single-use).
- `--max_rows` raised to 1,000,000: the bq default of 100 truncated column inventories — a
  pre-existing correctness bug fixed in passing because the argv was being rebuilt anyway.

### Pre-gate (local Artemis, FIX-FIRST, no blocker) — dispositions

- Fixed: loopback handler socket timeout (idle connection stalled `--timeout`); stray/forged-state
  callbacks now get 400 and the login keeps waiting; non-ASCII `state` compared as bytes;
  `SO_REUSEADDR` off + `SO_EXCLUSIVEADDRUSE` on Windows; token-dir rule above; origin-binding
  error names the API URL to pass; `outputs`/`dashboard` map token/API refusals to CLI errors via
  one helper (`cli/outputs.py:live_looker_graph`); docs' write table completed (build, chart,
  query navigate, conductor, validate log, clean deletions) and listener wording made exact.
- Filed as pre-existing (not this PR): dashboard Host-header / DNS-rebinding; `/tmp` chart writes
  follow symlinks.

### Gates

See the PR body for verbatim gate lines (ruff check, ruff format --check, mypy, pytest, dashboard
  JS check) and the mutation-control table.
