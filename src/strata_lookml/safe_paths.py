"""The one guard for files Strata replaces at a user-named path (baseline, IR cache).

Strata is read-only toward LookML. A write destination that is a symlink, a LookML source
file, a directory, or an existing file Strata did not write is refused before anything is
written, so a mistyped `--cache` / `--write-baseline` can never clobber a source file.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

LOOKML_SUFFIXES = frozenset({".lkml", ".lookml"})
SQLITE_MAGIC = b"SQLite format 3\x00"


def check_write_destination(path: Path, *, what: str, is_ours: Callable[[Path], bool]) -> Path:
    """The resolved destination, or `InvalidInput` if writing `what` there could clobber a file.

    Refuses a symlink final component, a `.lkml`/`.lookml` resolved path, a directory, and an
    existing file for which `is_ours` is false (it is not a previous `what` Strata wrote).
    """
    # Imported at raise time: errors.py pulls the MCP SDK, which must stay out of the L0
    # import graph (test_l0_no_network_imports).
    from strata_lookml.errors import InvalidInput

    if path.is_symlink():
        raise InvalidInput(f"refusing to write the {what} through a symlink: {path}")
    target = path.resolve()
    if target.suffix.lower() in LOOKML_SUFFIXES:
        raise InvalidInput(f"refusing to overwrite a LookML file with the {what}: {path}")
    if target.is_dir():
        raise InvalidInput(f"{what} destination is a directory: {path}")
    if target.exists() and not is_ours(target):
        raise InvalidInput(f"refusing to overwrite {path}: it is not a previous Strata {what}")
    return target


def is_sqlite_file(path: Path) -> bool:
    """True if the file starts with the SQLite 3 header."""
    try:
        with path.open("rb") as handle:
            return handle.read(len(SQLITE_MAGIC)) == SQLITE_MAGIC
    except OSError:
        return False
