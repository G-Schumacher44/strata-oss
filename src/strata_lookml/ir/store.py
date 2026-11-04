"""SQLite cache for resolved IR graphs."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from strata_lookml.ir.types import IRGraph

SCHEMA = """
CREATE TABLE IF NOT EXISTS ir_cache (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    built_at TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""


def save_ir(graph: IRGraph, cache_path: str | Path) -> None:
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    graph.cache_path = str(path)
    payload = json.dumps(graph.to_dict(), sort_keys=True)
    with sqlite3.connect(path) as conn:
        conn.execute(SCHEMA)
        conn.execute(
            """
            INSERT INTO ir_cache (id, built_at, payload)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET built_at = excluded.built_at, payload = excluded.payload
            """,
            (graph.built_at, payload),
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
