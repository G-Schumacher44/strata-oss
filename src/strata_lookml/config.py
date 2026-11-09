"""Shared configuration helpers — resolves env → ~/.strata/config.json → default."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

LEGACY_CACHE_NAME = "strata_ir.db"


def _read_config() -> dict:
    config_path = Path.home() / ".strata" / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def load_repo_path() -> Path:
    """Resolve repo path: STRATA_REPO_PATH env → ~/.strata/config.json → cwd."""
    env = os.environ.get("STRATA_REPO_PATH")
    if env:
        return Path(env).expanduser().resolve()
    data = _read_config()
    if data.get("repo_path"):
        return Path(data["repo_path"]).expanduser().resolve()
    return Path.cwd().resolve()


def load_bq_project() -> str | None:
    """Resolve BQ project: STRATA_BQ_PROJECT env → ~/.strata/config.json → None."""
    env = os.environ.get("STRATA_BQ_PROJECT")
    if env:
        return env
    return _read_config().get("bq_project")


def load_cost_threshold_gb() -> float:
    """Resolve BQ cost threshold: STRATA_COST_THRESHOLD_GB env → ~/.strata/config.json → 100.0."""
    env = os.environ.get("STRATA_COST_THRESHOLD_GB")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    return float(_read_config().get("cost_threshold_gb", 100.0))


def strata_home() -> Path:
    """Strata's per-user directory, ~/.strata (read at call time so HOME is honoured)."""
    return Path.home() / ".strata"


def repo_key(repo: str | Path) -> str:
    """`<repo-name>-<sha256(abs repo path)[:12]>`: names a repo's per-user files under
    ~/.strata (IR cache, validation log) so two repos that share a name never collide."""
    root = Path(repo).expanduser().resolve()
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    return f"{root.name}-{digest}"


def default_cache_path(repo: str | Path) -> Path:
    """Where a repo's IR cache lives when nothing overrides it:
    ~/.strata/cache/<repo_key>.db, outside the LookML checkout, one entry per repo."""
    return strata_home() / "cache" / f"{repo_key(repo)}.db"


def load_cache_path(repo: str | Path, cache: str | Path | None = None) -> Path:
    """Resolve the IR cache path: --cache → STRATA_CACHE_PATH env → default_cache_path(repo).

    The one resolver for every reader and writer of the cache (MCP server, `strata build`,
    `strata mcp validate|config`).
    """
    # abspath, not resolve(): a symlink at the named path must reach the writer's guard
    # (safe_paths.check_write_destination) as a symlink, not as its target.
    if cache:
        return Path(os.path.abspath(Path(cache).expanduser()))
    env = os.environ.get("STRATA_CACHE_PATH")
    if env:
        return Path(os.path.abspath(Path(env).expanduser()))
    return default_cache_path(repo)


def triage_path(repo: str | Path) -> Path:
    """Where a repo's triage store (acknowledged finding ids) lives:
    ~/.strata/triage/<repo_key>.json, outside the LookML checkout, one file per repo."""
    return strata_home() / "triage" / f"{repo_key(repo)}.json"


def ensure_private_dir(directory: Path, *, tighten: bool) -> None:
    """Create `directory` (and any missing parents) mode 0700 on POSIX.

    With `tighten`, an existing directory is chmod-ed to 0700 too; pass it only for a
    directory Strata owns. umask can only narrow mkdir's mode, so each new level is chmod-ed
    to exactly 0700.
    """
    missing = []
    level = directory
    while not level.exists():
        missing.append(level)
        level = level.parent
    for new_dir in reversed(missing):
        new_dir.mkdir(mode=0o700, exist_ok=True)
        if os.name == "posix":
            os.chmod(new_dir, 0o700)
    if tighten and not missing and os.name == "posix":
        os.chmod(directory, 0o700)
