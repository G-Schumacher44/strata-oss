# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-08-16 — feat/pypi-strata-lookml

Commit: (branch head at PR #18; anchored per-push — verify with `git log -1` on the branch)
Conductor Mode: slice
Context Budget: medium
Context Loaded: AGENTS.md, conductor/AGENTS.md, conductor/CONDUCTOR_MODES.md, conductor/index.md, conductor/slice-04-pypi-packaging.md, handoff-log latest block.
Context Skipped: handoff-archive.md.
Stage/DUOS: not used; not required.
Ledger: not applicable.
Tag Posture: no stable tag required (first `v0.1.6` tag is the post-merge publish trigger, operator-pushed).

**Governing spec:** `conductor/slice-04-pypi-packaging.md` (authored at the review gate's
direction — PR #18 Codex P1 — as the in-repo contract for this work).

**What changed:** Packaged strata-oss for PyPI distribution as `strata-lookml`
(the names `strata` and `strata-mcp` are taken on PyPI by unrelated projects; the tool stays
"Strata" everywhere, console scripts `strata`/`strata-mcp`/`strata-chart` unchanged).

- `pyproject.toml`: `name = "strata-lookml"`, version `0.1.5` → `0.1.6`, and — found during
  head-side verification — **`mcp>=1.0,<2`**: mcp 2.0 removed `mcp.server.fastmcp`, which
  `src/strata/mcp/server.py` imports, so the previous unbounded pin made every fresh install
  pull an SDK the server cannot import (`strata-mcp` dead-on-arrival while the other two
  commands worked). Upper-bounded with an in-file comment; the 2.x migration is follow-up work.
- `src/strata/cli/main.py`: `click.version_option(package_name="strata-lookml")` — Click
  resolves installed metadata by exact distribution name; the stale `"strata"` made
  `strata --version` raise post-rename (PR #18 Codex P2).
- `.github/workflows/release.yml`: `publish-pypi` job (needs `build-and-release`) using PyPI
  Trusted Publishing (OIDC) via `pypa/gh-action-pypi-publish@release/v1` — no stored token;
  artifact handoff so publish consumes the already-built `dist/`; `.mcpb` bundle build
  (`@anthropic-ai/mcpb` → `mcpb validate` → `mcpb pack`) attaching `strata-lookml.mcpb` to
  the GitHub Release.
- New `mcpb/` dir: spec-conformant `manifest.json` (`server.type: uv`, manifest 0.4), minimal
  `pyproject.toml` depending on `strata-lookml>=0.1.6`, 2-line `src/server.py` shim (the
  `.mcpb` `uv` runtime requires a local entry-point file; there is no published-package mode).
- `README.md`: Installation section (`uvx --from strata-lookml strata-mcp` — a bare
  `uvx strata-lookml` fails, no script matches the distribution name; `pipx`), Cursor +
  VS Code one-click install badges, top-of-file naming-split note.
- `.gitignore`: `*.mcpb`.
- Conductor: `slice-04-pypi-packaging.md` authored (status `review`), prior 07-18 handoff
  block moved to a new `conductor/handoff-archive.md`, `index.md` Active Slice pointer
  updated.

**What was verified — two-stage, honestly split:**

*Dispatch stage (sandboxed, no outbound network):* static only — TOML/JSON/YAML parsed,
`py_compile` clean, manifest hand-diffed against the live `modelcontextprotocol/mcpb` spec,
README regexes for `tests/test_docs_consistency.py` re-run by hand. Build/test explicitly
NOT run; disclosed rather than claimed.

*Head-side stage (full network, 2026-08-16):*
- `python -m build` → sdist + wheel build clean.
- **Fresh-venv wheel install** → `strata --version` reports `strata, version 0.1.6` (the P2
  fix, proven against installed metadata); `strata-chart` resolves; `strata-mcp` imports
  clean. This check is what CAUGHT the mcp 2.0 resolver break (resolver pulled mcp 2.0.0,
  `from mcp.server.fastmcp import FastMCP` failed; re-pinned `<2` → resolver picks 1.29.0,
  import clean, rebuilt + re-proven end-to-end).
- Full suite on an editable `[dev]` install: **106 passed**. `ruff check` clean on touched
  Python.
- Still unverified until the first tag push: the `publish-pypi` and `.mcpb` steps
  end-to-end (they can only run in CI on a tag) — watch that run, don't assume green.

**Operator prerequisite (blocking, before the first tag push):** configure the PyPI Trusted
Publisher at pypi.org — project `strata-lookml`, owner `G-Schumacher44`, repo `strata-oss`,
workflow `release.yml`, environment `pypi`. Without it `publish-pypi` fails closed with an
OIDC error — expected, not a bug (see the comment in `release.yml`).

**Also fixed on this branch (found by Apollo's required-checks blocker):** the
`tests/lookml/gcs_analytics` submodule pinned `cd9a4deb`, a commit its upstream no longer
has — the playground repo was recreated during the 2026-07-12 public bootstrap, orphaning
the pin, and `strata-ci` had never once run on `main`, so every PR checkout has been failing
at `actions/checkout` before tests could run. Repointed to the upstream head `f32aafa0`
(the playground's actual content — its repo holds 2 commits total). Suite re-run at the new
pin: 106 passed. Same dangling-ref shape as the pre-squash `anchor_ref` bug, third instance
of bootstrap-era rot (README URLs, default branch, now this).

**Exact Next Steps:**
1. Operator: configure the PyPI Trusted Publisher (above), then merge PR #18.
2. Operator (or Koa on instruction): push tag `v0.1.6` — first end-to-end proof of
   publish-pypi + `.mcpb`; watch the run.
3. Post-publish: `uvx --from strata-lookml strata-mcp` against a real MCP client once
   (closes the last slice-04 acceptance box); spot-check the Cursor/VS Code badges.
4. Follow-up (separate slice): migrate `src/strata/mcp/server.py` off `mcp.server.fastmcp`
   so the `<2` pin can lift; then registry submissions (official MCP registry, awesome-lists)
   per the distribution research (koa library, 2026-08-16).
