"""Run provenance and ref materialisation: which git ref an analysis covers.

Read-only git only (`rev-parse`, `symbolic-ref`, `status --porcelain`, `archive`): nothing here
writes to the user's repo, its `.git`, its refs or its worktrees.
"""

from __future__ import annotations

import os
import subprocess
import tarfile
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_GIT_TIMEOUT = 30
# `git status` refreshes and rewrites .git/index when file stat info changed (a touched mtime);
# optional locks off makes every call here a pure read. Set as both flag and env, belt and braces.
_GIT_PREFIX = ["git", "--no-optional-locks"]


def _git_env() -> dict[str, str]:
    return {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


def _git(repo: Path, *args: str) -> str | None:
    """stdout of a read-only git call, or None when git is absent, fails, or `repo` is no checkout."""
    try:
        proc = subprocess.run(
            [*_GIT_PREFIX, "-C", str(repo), *args],
            env=_git_env(),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def git_source(repo: str | Path) -> dict[str, Any] | None:
    """`{commit, branch, dirty}` for the checkout containing `repo`; None when not a git checkout.

    `branch` is "detached" on a detached HEAD. `dirty` covers tracked and untracked changes under
    `repo` itself (a LookML project can be a subdirectory of a larger checkout).
    """
    root = Path(repo)
    commit = _git(root, "rev-parse", "HEAD")
    if commit is None:
        return None
    branch = _git(root, "symbolic-ref", "--short", "-q", "HEAD")
    status = _git(root, "status", "--porcelain", "--untracked-files=normal", "--", ".")
    return {
        "commit": commit.strip(),
        "branch": branch.strip() if branch and branch.strip() else "detached",
        "dirty": bool(status and status.strip()),
    }


def resolve_commit(repo: str | Path, ref: str) -> str:
    """The commit `ref` names in `repo`; InvalidInput (with a hint) when it does not resolve."""
    from strata_lookml.errors import InvalidInput

    if _git(Path(repo), "rev-parse", "--show-toplevel") is None:
        raise InvalidInput(
            f"not a git checkout: {repo}", hint="`strata diff` compares refs of a git repository."
        )
    # A ref that begins with "-" must never reach git as an option.
    commit = (
        None
        if ref.startswith("-")
        else _git(Path(repo), "rev-parse", "--verify", f"{ref}^{{commit}}")
    )
    if commit is None:
        raise InvalidInput(
            f"unknown git ref: {ref}",
            hint="Pass a branch, tag or commit that exists locally (try `git fetch` for a remote ref).",
        )
    return commit.strip()


@contextmanager
def materialised(repo: str | Path, commit: str) -> Iterator[Path]:
    """The LookML project at `commit`, exported read-only into a temp dir that is removed on exit.

    `git archive <commit>` streamed into a tar extraction under the system temp: no worktree, ref
    or file is created in the user's repo. `git archive` leaves submodule contents out and
    honours `export-ignore` attributes. Run from `repo`, it exports `repo`'s own subtree, so a
    LookML project below the checkout root comes out rooted at the temp dir.
    """
    from strata_lookml.errors import InvalidInput

    root = Path(repo)
    with tempfile.TemporaryDirectory(prefix="strata-diff-") as tmp:
        try:
            proc = subprocess.Popen(
                [*_GIT_PREFIX, "-C", str(root), "archive", "--format=tar", commit],
                env=_git_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise InvalidInput(f"git is not available: {exc}") from exc
        assert proc.stdout is not None and proc.stderr is not None
        try:
            with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
                tar.extractall(tmp, filter="data")
        except (tarfile.TarError, OSError) as exc:
            proc.kill()
            raise InvalidInput(f"could not export {commit[:7]} from git: {exc}") from exc
        finally:
            proc.stdout.close()
            err = proc.stderr.read().decode(errors="replace").strip()
            proc.stderr.close()
            code = proc.wait()
        if code != 0:
            raise InvalidInput(f"git archive failed for {commit[:7]}: {err}")
        yield Path(tmp)
