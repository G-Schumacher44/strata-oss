# Handoff Log

Current active handoff block only — older entries move to `handoff-archive.md`.

## 2026-07-18 — bughunt/find-field-truncation-flag

**What changed:** Fixed the `strata_find_field` truncated-flag off-by-one in
`src/strata/mcp/tools.py`. `len(matches)` can never exceed the 50-item cap, so
`"truncated": len(matches) >= 50` wrongly reported `truncated=true` at exactly
50 matches (nothing was actually omitted). Now a `total` counter is
incremented for every match while `matches` still only appends the first 50;
`truncated = total > 50`.

**What was verified:**
- Added `test_strata_find_field_truncated_flag_false_at_exactly_fifty_matches`
  (50 matches → `truncated is False`).
- Negative control: stashed the source fix (kept the test) and confirmed the
  new test fails against the old `>= 50` logic.
- Full suite: 105 passed. `ruff check` and `mypy` clean on changed files.

**What remains / exact next step:**
- Direct push to `bughunt/find-field-truncation-flag` is blocked — it is
  currently this repo's default branch, and ruleset `main`
  (targets `~DEFAULT_BRANCH`, no bypass) requires all changes to land via PR.
  Opened PR #13 (`bughunt/find-field-truncation-flag-fix-truncated-boundary` →
  `bughunt/find-field-truncation-flag`) to carry the commit onto this branch;
  merging #13 updates PR #9 automatically. Left a status comment on PR #9;
  did not resolve the Codex thread there (out of scope for this task).
- Operator action needed: merge PR #13 (dispatched agents don't merge).

## 2026-08-16 — feat/pypi-strata-lookml

**What changed:** Packaged strata-oss for PyPI distribution as `strata-lookml`
(name `strata` and `strata-mcp` were already taken by unrelated projects; the
tool stays "Strata" everywhere, console scripts `strata`/`strata-mcp`/
`strata-chart` are unchanged).
- `pyproject.toml`: `name = "strata-lookml"`, version bumped `0.1.5` → `0.1.6`.
- `.github/workflows/release.yml`: new `publish-pypi` job (needs
  `build-and-release`) using PyPI Trusted Publishing (OIDC) via
  `pypa/gh-action-pypi-publish@release/v1` — no stored token. Added
  `actions/upload-artifact`/`download-artifact` so publish only consumes the
  already-built `dist/`. Added an MCP Bundle (`.mcpb`) build step (installs
  `@anthropic-ai/mcpb`, `mcpb validate` then `mcpb pack`) to the same job,
  attaching `strata-lookml.mcpb` to the GitHub Release alongside `dist/*`.
- New `mcpb/` directory: `manifest.json` (server.type `uv`, manifest_version
  `0.4`), a minimal `pyproject.toml` declaring `strata-lookml>=0.1.6` as a
  dependency, and a two-line `src/server.py` shim that imports and calls the
  real `strata.mcp.server:main`. See `mcpb/README.md` for why a shim (the
  `.mcpb` `uv` runtime spec requires a local `entry_point` file — it has no
  "point at a published PyPI package" mode).
- `README.md`: new Installation section (`uvx`/`pipx`, MCP client config
  reflecting the real entry point via `uvx --from strata-lookml strata-mcp`,
  Cursor + VS Code one-click install badges) plus a top-of-file note on the
  strata-lookml/Strata naming split.
- `.gitignore`: added `*.mcpb`.

**What was verified (and what could NOT be, with why):**
- `pyproject.toml` / `mcpb/pyproject.toml`: parsed with stdlib `tomllib` —
  valid. `mcpb/manifest.json`: valid JSON, hand-diffed against the current
  `modelcontextprotocol/mcpb` spec (`MANIFEST.md` + `examples/hello-world-uv`,
  fetched live) field-by-field. `release.yml`: parsed with `pyyaml` — valid.
  `mcpb/src/server.py`: `py_compile` clean.
  Confirmed via `pypa/gh-action-pypi-publish`'s live README that
  `permissions: id-token: write` + `environment:` + no username/password is
  still the current trusted-publishing pattern, and confirmed
  `anthropics/mcpb` now redirects to `modelcontextprotocol/mcpb` (used the
  new org in README/handoff links).
  Checked `tests/test_docs_consistency.py`'s README-parsing regexes by hand —
  my additions don't touch the tool/CLI/skills tables those tests assert
  against, and re-ran the same regexes against the edited README locally
  (18 tool rows, 15 CLI rows — unchanged counts).
- **Could NOT run:** `python -m build`/`uv build`, `pip install dist/*.whl`,
  `pytest`, `ruff`, `mypy`, or `mcpb validate`/`mcpb pack` locally. This
  dispatch's sandbox has no outbound network (pip/npm index access denied;
  `dangerouslyDisableSandbox` was granted for a handful of doc-fetch calls
  then stopped being granted for the rest of the session) and `uv` itself
  panics on any invocation in this sandbox (`system-configuration` crate hits
  a blocked macOS SystemConfiguration call and aborts, even for `uv venv`
  with no network involved) — so the project's own test/build deps (`mcp`,
  `networkx`, etc.) could not be installed by any means available here.
  **No source under `src/` changed** — the touched surface is packaging
  metadata, CI YAML, docs, and a new stand-alone `mcpb/` dir not on any lint
  path (`strata-ci.yml` lints `src/ tests/ scripts/` only), so the blast
  radius of an unverified build is low, but it is genuinely unverified.
  `build-and-release` and `strata-ci` jobs are unchanged in what they already
  did successfully before this PR (only appended steps/a new job), so CI
  should still surface any real breakage on this PR.
- Cursor (`cursor://anysphere.cursor-deeplink/mcp/install`) and VS Code
  (`vscode:mcp/install`) badge URL schemes: authored from documented/training
  knowledge; the encoded payloads were generated deterministically and
  round-trip-decoded locally to confirm they carry the intended JSON, but the
  schemes themselves were not re-confirmed against live docs this session
  (same network blocker). Flagged inline in the README as a verification
  note asking for a one-time spot-check.

**Operator prerequisite (blocking, before the first tag push):** configure a
PyPI Trusted Publisher at pypi.org for project `strata-lookml`, owner
`G-Schumacher44`, repo `strata-oss`, workflow `release.yml`, environment
`pypi`. Without it, `publish-pypi` fails closed with an OIDC/"not a trusted
publisher" error — expected, not a bug (see the comment in `release.yml`).

**What remains / exact next step:**
- Operator: run `python -m build` (or `uv build`) + `pip install dist/*.whl`
  in a normal (non-sandboxed) shell once, confirm the three console scripts
  resolve, before merging — this PR's own claim of "builds cleanly" is
  unverified per above.
- Operator: configure the PyPI Trusted Publisher (see prerequisite above)
  before pushing the first `v0.1.6` tag.
- Operator: spot-check the Cursor and VS Code install badges in the README
  once against a real Cursor/VS Code install.
- First tag push will be the first real end-to-end proof of the `.mcpb`
  build step; watch that CI run once rather than assuming green.
