"""SQLite cache for resolved IR graphs.

The cache records the inputs it was built from (repo path, fixture paths + mtimes), so a
reader can tell a cache built for other inputs from a fresh one (`cache_is_fresh`).
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from strata_lookml.config import ensure_private_dir, strata_home
from strata_lookml.ir.types import IRGraph

SCHEMA = """
CREATE TABLE ir_cache (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    built_at TEXT NOT NULL,
    inputs TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""


def describe_inputs(
    repo_path: str | Path,
    usage_fixture: str | Path | None = None,
    schema_fixture: str | Path | None = None,
) -> dict[str, Any]:
    """The inputs a graph is built from, normalised so a writer and a reader compare equal.

    A fixture is recorded with its mtime, so editing it in place invalidates the cache. A
    missing fixture records mtime None (the build itself then fails loudly).
    """

    def fixture(path: str | Path | None) -> dict[str, Any] | None:
        if not path:
            return None
        resolved = Path(path).expanduser().resolve()
        try:
            mtime_ns: int | None = resolved.stat().st_mtime_ns
        except OSError:
            mtime_ns = None
        return {"path": str(resolved), "mtime_ns": mtime_ns}

    return {
        "repo": str(Path(repo_path).expanduser().resolve()),
        "usage_fixture": fixture(usage_fixture),
        "schema_fixture": fixture(schema_fixture),
    }


def save_ir(graph: IRGraph, cache_path: str | Path, inputs: dict[str, Any] | None = None) -> None:
    """Write the graph as the cache's single row, file mode 0600.

    A missing directory is created 0700; Strata's own ~/.strata/cache is tightened to 0700. A
    cache from an older schema is replaced, not migrated (the cache is disposable).
    """
    path = Path(cache_path)
    cache_dir = strata_home() / "cache"
    ensure_private_dir(path.parent, tighten=path.parent.resolve() == cache_dir.resolve())
    # Create the file 0600 before sqlite opens it (sqlite would create it 0644 & ~umask);
    # sqlite's journal inherits the database file's mode.
    os.close(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600))
    if os.name == "posix":
        os.chmod(path, 0o600)
    graph.cache_path = str(path)
    payload = json.dumps(graph.to_dict(), sort_keys=True)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE IF EXISTS ir_cache")
        conn.execute(SCHEMA)
        conn.execute(
            "INSERT INTO ir_cache (id, built_at, inputs, payload) VALUES (1, ?, ?, ?)",
            (graph.built_at, json.dumps(inputs, sort_keys=True), payload),
        )


def load_ir(cache_path: str | Path) -> IRGraph:
    path = Path(cache_path)
    with _connect_existing(path) as conn:
        row = conn.execute("SELECT payload FROM ir_cache WHERE id = 1").fetchone()
    if row is None:
        raise FileNotFoundError(f"IR cache has no payload: {path}")
    graph = IRGraph.from_dict(json.loads(row[0]))
    graph.cache_path = str(path)
    return graph


def cache_age_seconds(cache_path: str | Path) -> float | None:
    path = Path(cache_path)
    try:
        conn = _connect_existing(path)
    except FileNotFoundError:
        return None
    with conn:
        row = conn.execute("SELECT built_at FROM ir_cache WHERE id = 1").fetchone()
    if row is None:
        return None
    try:
        built_at = datetime.fromisoformat(row[0])
    except (TypeError, ValueError):
        return None
    if built_at.tzinfo is None:
        built_at = built_at.replace(tzinfo=UTC)
    age = (datetime.now(UTC) - built_at).total_seconds()
    # A future built_at (clock skew or a hand-edited cache) would read as "fresh" forever;
    # report no usable age so the caller rebuilds.
    return age if age >= 0 else None


def cache_inputs(cache_path: str | Path) -> dict[str, Any] | None:
    """The inputs a cache recorded, or None (missing file, no row, pre-inputs schema)."""
    try:
        conn = _connect_existing(Path(cache_path))
    except FileNotFoundError:
        return None
    with conn:
        try:
            row = conn.execute("SELECT inputs FROM ir_cache WHERE id = 1").fetchone()
        except sqlite3.OperationalError:
            return None  # an older cache without the inputs column
    if row is None:
        return None
    try:
        inputs = json.loads(row[0])
    except (TypeError, ValueError):
        return None
    return inputs if isinstance(inputs, dict) else None


def cache_is_fresh(cache_path: str | Path, inputs: dict[str, Any], max_age_seconds: float) -> bool:
    """True only when the cache was built from exactly `inputs` and is younger than the max."""
    age = cache_age_seconds(cache_path)
    if age is None or age >= max_age_seconds:
        return False
    return cache_inputs(cache_path) == inputs


def _connect_existing(path: Path) -> sqlite3.Connection:
    """Open an existing cache read-write without ever creating it.

    A plain sqlite3.connect creates an empty ghost file when the path is missing, and an
    exists() check before it races a concurrent `strata clean`. mode=rw makes the open
    itself fail atomically instead.
    """
    try:
        return sqlite3.connect(f"{path.resolve().as_uri()}?mode=rw", uri=True)
    except sqlite3.OperationalError as exc:
        if not path.exists():
            raise FileNotFoundError(f"IR cache not found: {path}") from exc
        raise
