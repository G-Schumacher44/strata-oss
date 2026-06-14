# Public Release Flow

Strata has two publication boundaries:

- `origin/dev` is the private live working branch.
- `origin/main` is the private release branch.
- `public/main` is a sanitized OSS export branch on the `public` remote.

Do not treat `public/main` as a mirror of `origin/main` or `origin/dev`.
Publishing to `public` is an explicit export operation.

## Why This Exists

The Conductor working state is branch-specific. `dev` can contain active slices,
handoffs, benchmark notes, local repo names, and operator context that should not
automatically ship to the public repository. The `.gitattributes` merge driver
protects local private merges by keeping selected Conductor files from drifting
from `dev` into private `main`, but it does not sanitize a public repository by
itself.

Public release safety comes from this flow:

1. Start from `public/main`.
2. Bring over only the approved release surface.
3. Run the public release audit.
4. Review the full diff.
5. Push only the dedicated public release branch or `public/main`.

## Required Local Setup

For private local `dev -> main` promotions, activate the custom merge driver
once per clone:

```bash
git config merge.ours.driver true
```

This setting only affects local merges. It does not run on GitHub and it does
not replace the public release audit.

## Recommended Public Worktree

Use a separate worktree so private branch state and public export state are not
mixed in one checkout:

```bash
git fetch origin
git fetch public
git worktree add ../strata-public-release public/main
cd ../strata-public-release
git switch -c public-release/$(date +%Y%m%d)
```

From that worktree, copy or restore only approved files from the private release
commit. Example:

```bash
git restore --source origin/main -- README.md docs src tests pyproject.toml
```

Adjust the path list for each release. Do not bulk-merge `origin/main` into the
public branch unless the resulting diff has been reviewed and audited.

## Audit Before Push

Run the audit from the main private checkout or the public-release worktree:

```bash
python scripts/check_public_release.py --base public/main --target HEAD
```

The check fails when the candidate release includes private Conductor working
files, local machine paths, common credential markers, or other high-risk paths.
Path-based blockers are governed by `.publicignore`. It is intentionally
conservative. Fix the candidate branch, then rerun it.

### Troubleshooting Audit Failures

- **`matches private path rule`**: A file is present that should remain private.
  Remove it from the candidate branch (`git rm`) or ensure it is covered by
  `.publicignore`.
- **`contains local machine path`**: A file contains a hardcoded path like
  `/ Vol` + `umes /` or `/ Us` + `ers /`. Use relative paths or environment variables instead.
- **`public baseline ref not found`**: Ensure you have run `git fetch public` and
  that your remote is named `public`.
- **False Positives**: The audit script excludes itself and its tests from content
  searches. If you find a false positive in another file, sanitize the file
  rather than bypassing the audit.

The same check runs in GitHub Actions via `.github/workflows/public-release-audit.yml`
for:

- `workflow_dispatch`
- pushes to `public-release/**`
- tags matching `public-v*`

Use the workflow as a release gate. It does not publish to the public repository.
If a `public-v*` tag is created on private `main`, the audit should fail because
private-only Conductor state is still present. Tag the sanitized public release
candidate instead.

To run it manually through the GitHub UI:

1. Open **Actions**.
2. Select **Public release audit**.
3. Select **Run workflow**.
4. Choose the private default branch that contains the workflow.
5. Set `target_ref` to the public candidate ref, for example
   `public/public-release/YYYYMMDD`.
6. Leave `public_base` as `public/main` unless intentionally comparing against a
   different public baseline.

Also inspect the full diff before pushing:

```bash
git diff --stat public/main..HEAD
git diff --name-status public/main..HEAD
```

## Push

After the audit passes and the diff is reviewed:

```bash
git push public HEAD:main
```

For a reviewable public PR branch instead:

```bash
git push public HEAD:public-release/YYYYMMDD
```

## Rules For Agents

- Never push `origin/main` or `origin/dev` directly to `public/main`.
- Never use the GitHub merge button to promote private `dev -> main`; local
  merge drivers do not run on GitHub.
- Treat public publishing as a release export, not branch synchronization.
- Keep `.publicignore` current when new private-only paths are added.
- Run `scripts/check_public_release.py` before any public push.
- Treat the public release audit workflow as a required gate for public release
  branches or tags.
