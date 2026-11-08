"""SQLite cache for resolved IR graphs.

The cache records the inputs it was built from (repo path + .lkml fingerprint, fixture
paths + mtimes), so a reader can tell a cache built for other inputs from a fresh one
(`cache_is_fresh`).
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
import warnings
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from strata_lookml.config import ensure_private_dir, strata_home
from strata_lookml.ir.parser import lkml_paths
from strata_lookml.ir.types import IRGraph
from strata_lookml.safe_paths import check_write_destination

SCHEMA = """
CREATE TABLE ir_cache (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    built_at TEXT NOT NULL,
    inputs TEXT NOT NULL,
    payload TEXT NOT NULL
)
"""

_SQLITE_MAGIC = b"SQLite format 3\x00"
# Columns every Strata cache has had; `inputs` was added with the input-keyed reuse.
_CACHE_COLUMNS = frozenset({"id", "built_at", "payload"})
_REPLACE_ATTEMPTS = 3
_REPLACE_BACKOFF_SECONDS = 0.05


def describe_inputs(
    repo_path: str | Path,
    usage_fixture: str | Path | None = None,
    schema_fixture: str | Path | None = None,
) -> dict[str, Any]:
    """The inputs a graph is built from, normalised so a writer and a reader compare equal.

    A fixture is recorded with its mtime, so editing it in place invalidates the cache. A
    missing fixture records mtime None (the build itself then fails loudly). The repo is
    recorded by path plus `lookml_fingerprint`, so a .lkml edit invalidates it too.
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

    repo = Path(repo_path).expanduser().resolve()
    return {
        "repo": str(repo),
        "lookml": lookml_fingerprint(repo),
        "usage_fixture": fixture(usage_fixture),
        "schema_fixture": fixture(schema_fixture),
    }


def lookml_fingerprint(repo: Path) -> dict[str, Any]:
    """A cheap stat-only fingerprint of the .lkml files the IR is built from.

    Uses the parser's own discovery (`lkml_paths`), so it covers exactly the files a build
    reads: count, newest mtime, total size, and a hash of the relative paths (a rename or
    move changes source_file citations even when no content changes).
    """
    paths = lkml_paths(repo) if repo.is_dir() else []
    max_mtime_ns = 0
    total_size = 0
    names = hashlib.sha256()
    for path in paths:
        st = path.stat()
        max_mtime_ns = max(max_mtime_ns, st.st_mtime_ns)
        total_size += st.st_size
        names.update(str(path.relative_to(repo)).encode("utf-8") + b"\0")
    return {
        "count": len(paths),
        "max_mtime_ns": max_mtime_ns,
        "total_size": total_size,
        "paths_sha256": names.hexdigest(),
    }


def save_ir(graph: IRGraph, cache_path: str | Path, inputs: dict[str, Any] | None = None) -> None:
    """Write the graph as the cache's single row, file mode 0600, replacing the file atomically.

    The new cache is written to a temp file beside the target and `os.replace`d over it, so a
    concurrent reader sees the previous complete cache or the new one, never a half-written
    state, and an interrupted write leaves the old cache untouched. If the swap keeps failing
    (Windows, a reader holding the file open) the temp file is dropped, the old cache kept,
    and a RuntimeWarning emitted; the build itself never fails on it. A destination that is a
    symlink, LookML source, a directory or (outside ~/.strata/cache) any existing file that is
    not a Strata IR cache — including an unrelated SQLite database — is refused (`InvalidInput`) before anything is written. Whatever was at the path
    before (an older schema, a corrupt file) is replaced, not migrated (the cache is
    disposable). A missing directory is created 0700; Strata's own ~/.strata/cache is
    tightened to 0700.
    """
    cache_dir = strata_home() / "cache"

    def is_ours(target: Path) -> bool:
        # Anything in Strata's own cache dir is Strata's (a damaged entry is rebuilt); at a
        # user-named path only an existing Strata IR cache may be replaced.
        return target.parent == cache_dir.resolve() or is_strata_cache(target)

    path = check_write_destination(Path(cache_path), what="IR cache", is_ours=is_ours)
    ensure_private_dir(path.parent, tighten=path.parent.resolve() == cache_dir.resolve())
    graph.cache_path = str(path)
    payload = json.dumps(graph.to_dict(), sort_keys=True)
    tmp = path.parent / f".{path.name}.{secrets.token_hex(8)}.tmp"
    # Created 0600 with O_EXCL before sqlite opens it (sqlite would create it 0644 & ~umask);
    # sqlite's journal inherits the database file's mode.
    os.close(os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
    try:
        conn = sqlite3.connect(tmp)
        try:
            with conn:
                conn.execute(SCHEMA)
                conn.execute(
                    "INSERT INTO ir_cache (id, built_at, inputs, payload) VALUES (1, ?, ?, ?)",
                    (graph.built_at, json.dumps(inputs, sort_keys=True), payload),
                )
        finally:
            conn.close()
        replaced = _replace_with_retry(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    if not replaced:
        tmp.unlink(missing_ok=True)
        warnings.warn(
            f"IR cache not updated: could not replace {path} (another process may have it "
            "open); the previous cache is kept and the next start rebuilds if it is stale",
            RuntimeWarning,
            stacklevel=2,
        )


def is_strata_cache(path: Path) -> bool:
    """True only for a SQLite file holding Strata's `ir_cache` table (current or older schema).

    Opened read-only (`mode=ro`) and closed explicitly, so checking never creates, locks for
    write, or modifies the file. Any other SQLite database is not ours to replace.
    """
    try:
        with path.open("rb") as handle:
            if handle.read(len(_SQLITE_MAGIC)) != _SQLITE_MAGIC:
                return False
        conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    except (OSError, sqlite3.DatabaseError):
        return False
    try:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if tables != {"ir_cache"}:
            return False
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ir_cache)")}
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()
    return _CACHE_COLUMNS <= columns <= _CACHE_COLUMNS | {"inputs"}


def _replace_with_retry(tmp: Path, path: Path) -> bool:
    """os.replace, retried briefly; False if it never succeeds.

    On Windows a file another process has open cannot be replaced (a sharing violation,
    PermissionError) until that reader closes it. The cache is an optimisation, so a swap
    that keeps failing is reported to the caller instead of failing the build.
    """
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(tmp, path)
            return True
        except OSError:
            if attempt + 1 < _REPLACE_ATTEMPTS:
                time.sleep(_REPLACE_BACKOFF_SECONDS * (attempt + 1))
    return False


def load_ir(cache_path: str | Path) -> IRGraph:
    path = Path(cache_path)
    # closing(): sqlite3's own context manager ends the transaction but leaves the connection
    # open, and an open handle blocks the next save_ir's replace on Windows.
    with closing(_connect_existing(path)) as conn:
        row = conn.execute("SELECT payload FROM ir_cache WHERE id = 1").fetchone()
    if row is None:
        raise FileNotFoundError(f"IR cache has no payload: {path}")
    graph = IRGraph.from_dict(json.loads(row[0]))
    graph.cache_path = str(path)
    return graph


def cache_age_seconds(cache_path: str | Path) -> float | None:
    row = _read_cache_column(Path(cache_path), "built_at")
    if row is None:
        return None
    try:
        built_at = datetime.fromisoformat(row)
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
    row = _read_cache_column(Path(cache_path), "inputs")
    if row is None:
        return None
    try:
        inputs = json.loads(row)
    except (TypeError, ValueError):
        return None
    return inputs if isinstance(inputs, dict) else None


def cache_is_fresh(cache_path: str | Path, inputs: dict[str, Any], max_age_seconds: float) -> bool:
    """True only when the cache was built from exactly `inputs` and is younger than the max."""
    age = cache_age_seconds(cache_path)
    if age is None or age >= max_age_seconds:
        return False
    return cache_inputs(cache_path) == inputs


def _read_cache_column(path: str | Path, column: Literal["built_at", "inputs"]) -> Any:
    """One column of the cache row, or None when there is no usable cache.

    A missing file, a missing row, a missing table or column (an older or hand-damaged
    cache) and a file that is not a SQLite database are all a cache miss: the caller
    rebuilds rather than failing.
    """
    try:
        conn = _connect_existing(Path(path))
    except (FileNotFoundError, sqlite3.DatabaseError):
        return None
    try:
        row = conn.execute(f"SELECT {column} FROM ir_cache WHERE id = 1").fetchone()
    except sqlite3.DatabaseError:
        return None
    finally:
        conn.close()
    return None if row is None else row[0]


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
