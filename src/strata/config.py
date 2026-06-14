"""Shared configuration helpers — resolves env → ~/.strata/config.json → default."""

from __future__ import annotations

import json
import os
from pathlib import Path


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
