"""Triage state for the workbench and TUI: which findings an engineer has acknowledged.

Plain Python, front-end agnostic: the web workbench and the TUI both read `triage_rows`, and
neither this module nor `links` may import an HTTP server, a renderer or a TUI toolkit
(tests/test_triage.py guards the import graph).

Only "acknowledged" is stored, in `~/.strata/triage/<repo_key>.json`, outside the repo. Every
other status is derived (`triage_rows`). The store never feeds `strata check`: the gate stays on
the committed baseline, so CI never depends on one engineer's local state.

The document is `{version, rev, ids: {id: {category, acked_at, note?, unacked_at?,
first_absent_at?}}}` and is append-only: unacknowledging sets `unacked_at` and keeps the entry;
an entry is removed only once its id has been absent, from a category whose check ran, for
`ABSENT_TTL`. Writes are serialized by an OS advisory lock on `<store>.lock` (`fcntl.flock` on
POSIX, `msvcrt.locking` on Windows) held around the rev check and the replace; the kernel releases
it when its holder dies, so there is no stale-lock handling and the lock file is never deleted.
Optimistic concurrency on `rev` stays as defence in depth: re-read, apply per id, and replace only
if `rev` is still the one read, retrying `_RETRIES` times.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from strata_lookml.config import ensure_private_dir, strata_home, triage_path
from strata_lookml.errors import InvalidInput, StrataError
from strata_lookml.gate import FINDING_CATEGORIES, INTEGRITY, finding_records
from strata_lookml.ir.types import IRGraph
from strata_lookml.l1.enrich import analysis_coverage
from strata_lookml.safe_paths import check_write_destination

TRIAGE_VERSION = 1
ABSENT_TTL = timedelta(days=90)
MAX_NOTE_CHARS = 2000
_RETRIES = 3
_BACKOFF_S = 0.05

Status = Literal["new", "acknowledged", "baselined", "fixed", "not_checked"]


@dataclass(frozen=True)
class TriageRow:
    """One finding id as a triage list shows it, its status derived once (`triage_rows`).

    A fixed or not-checked id has no current record, so its label is the id and its subject,
    file and line are None.
    """

    id: str
    category: str
    label: str
    message: str
    subject_id: str | None
    source_file: str | None
    source_line: int | None
    status: Status
    acked_at: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class _Findings:
    """What one graph says right now: each current finding id's category, and the categories
    whose check ran (integrity always; an opt-in category only when its facts were loaded)."""

    current: Mapping[str, str]
    checked: frozenset[str]

    @classmethod
    def of(cls, graph: IRGraph) -> _Findings:
        current: dict[str, str] = {}
        for record in finding_records(graph):
            current.setdefault(record["id"], record["category"])
        # Each category's own facts decide (FINDING_CATEGORIES): usage for dead-code and the
        # PDT categories, schema for drift. Content references feed dead code but gate nothing.
        coverage = analysis_coverage(graph)
        ran = {c for c, facts in FINDING_CATEGORIES.items() if coverage[facts]}
        return cls(current, frozenset(ran | {INTEGRITY}))


def _empty_document() -> dict[str, Any]:
    return {"version": TRIAGE_VERSION, "rev": 0, "ids": {}}


def _read_document(path: Path) -> dict[str, Any]:
    """The store at `path` (an empty one if there is no file); `InvalidInput` if it is a
    symlink or not a Strata triage store."""
    if path.is_symlink():
        raise InvalidInput(f"refusing to read the triage store through a symlink: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _empty_document()
    except OSError as exc:
        raise InvalidInput(f"cannot read triage store {path}: {exc}") from exc
    try:
        document = json.loads(text)
    except ValueError:
        document = None
    if not _valid(document):
        raise InvalidInput(
            f"{path} is not a version {TRIAGE_VERSION} Strata triage store",
            hint="Move the file aside; acknowledgements start again from empty.",
        )
    return document


def _valid(document: Any) -> bool:
    if not isinstance(document, dict) or document.get("version") != TRIAGE_VERSION:
        return False
    rev, ids = document.get("rev"), document.get("ids")
    if not isinstance(rev, int) or isinstance(rev, bool) or rev < 0 or not isinstance(ids, dict):
        return False
    return all(
        isinstance(entry, dict)
        and isinstance(entry.get("category"), str)
        and _is_stamp(entry.get("acked_at"))
        and all(_is_stamp(entry[key]) for key in ("unacked_at", "first_absent_at") if key in entry)
        and isinstance(entry.get("note", ""), str)
        for entry in ids.values()
    )


def _is_stamp(value: Any) -> bool:
    """An ISO-8601 timestamp with a UTC offset, as `_stamp` writes."""
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def _current_rev(path: Path) -> int:
    """The store's `rev` as it is on disk now (the pre-replace concurrency check)."""
    return int(_read_document(path)["rev"])


def _is_lock_file(path: Path) -> bool:
    """A triage lock file: empty, since nothing is ever written to it."""
    return path.is_file() and path.stat().st_size == 0


@contextmanager
def _exclusive(lock: Path) -> Iterator[None]:
    """Hold the store's write lock: an OS advisory lock on `lock`, created 0600 if missing and
    never deleted. Blocks while another writer holds it (Windows: `msvcrt` retries for ~10 s,
    then `StrataError`); released by the kernel if the holder dies."""
    target = check_write_destination(lock, what="triage lock", is_ours=_is_lock_file)
    fd = os.open(target, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            except OSError as exc:
                raise StrataError(
                    f"triage store is locked by another writer: {lock}", hint="retry"
                ) from exc
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _is_triage_store(path: Path) -> bool:
    try:
        _read_document(path)
    except InvalidInput:
        return False
    return True


def _stamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds")


def _id_list(ids: Iterable[str]) -> list[str]:
    if isinstance(ids, str) or not isinstance(ids, Iterable):
        raise InvalidInput("ids must be a list of finding ids")
    items = list(ids)
    if not all(isinstance(i, str) and i for i in items):
        raise InvalidInput("every finding id must be a non-empty string")
    return list(dict.fromkeys(items))


def _unknown(ids: list[str]) -> InvalidInput:
    shown = ", ".join(repr(i) for i in ids[:5]) + (", ..." if len(ids) > 5 else "")
    return InvalidInput(
        f"not a current finding id: {shown}",
        hint="Acknowledge only ids the current findings report (or ids already stored).",
    )


class TriageStore:
    """One repo's acknowledgements, bound to the findings of the graph it was opened with.

    The graph is the allowlist: `acknowledge` accepts an id only if a current finding carries
    it or the store already holds it, so a request can never plant arbitrary ids.
    """

    def __init__(
        self, path: Path, findings: _Findings, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._path = path
        self._findings = findings
        self._clock = clock or (lambda: datetime.now(UTC))

    @classmethod
    def open(
        cls, repo: str | Path, graph: IRGraph, *, clock: Callable[[], datetime] | None = None
    ) -> TriageStore:
        """The store for `repo` (`config.triage_path`); nothing is written until a change."""
        return cls(triage_path(repo), _Findings.of(graph), clock)

    @property
    def path(self) -> Path:
        return self._path

    def snapshot(self) -> dict[str, Any]:
        """A copy of the stored document (an empty one when nothing has been stored)."""
        return copy.deepcopy(_read_document(self._path))

    def acknowledge(self, ids: Iterable[str], note: str | None = None) -> None:
        """Acknowledge each id (re-acknowledging clears `unacked_at`); `note` replaces the
        stored note when given. Any id outside the allowlist -> `InvalidInput`, nothing written."""
        wanted = _id_list(ids)
        if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE_CHARS):
            raise InvalidInput(f"note must be a string of at most {MAX_NOTE_CHARS} characters")

        def apply(stored: dict[str, Any]) -> bool:
            unknown = [i for i in wanted if i not in self._findings.current and i not in stored]
            if unknown:
                raise _unknown(unknown)
            now = _stamp(self._clock())
            for finding_id in wanted:
                entry = stored.setdefault(
                    finding_id, {"category": self._findings.current.get(finding_id)}
                )
                entry["acked_at"] = now
                entry.pop("unacked_at", None)
                if finding_id in self._findings.current:
                    # Present now: a later absence starts a fresh retention period.
                    entry.pop("first_absent_at", None)
                if note is not None:
                    entry["note"] = note
            return bool(wanted)

        self._mutate(apply)

    def unacknowledge(self, ids: Iterable[str]) -> None:
        """Mark each stored id unacknowledged (`unacked_at`); the entry is kept. An id the
        store does not hold -> `InvalidInput`, nothing written."""
        wanted = _id_list(ids)

        def apply(stored: dict[str, Any]) -> bool:
            unknown = [i for i in wanted if i not in stored]
            if unknown:
                raise _unknown(unknown)
            now = _stamp(self._clock())
            changed = False
            for finding_id in wanted:
                if "unacked_at" not in stored[finding_id]:
                    stored[finding_id]["unacked_at"] = now
                    changed = True
            return changed

        self._mutate(apply)

    def observe(self) -> dict[str, Any]:
        """Record what the bound graph shows, then return `snapshot()`.

        For every stored id in a category whose check ran: present clears `first_absent_at`;
        absent stamps it on first sight; absent for `ABSENT_TTL` removes the entry. Ids in a
        category that was not checked are left alone (unknown is never absent). Writes only
        when something changed.
        """
        now = self._clock()

        def apply(stored: dict[str, Any]) -> bool:
            changed = False
            for finding_id, entry in list(stored.items()):
                if entry["category"] not in self._findings.checked:
                    continue
                if finding_id in self._findings.current:
                    changed |= entry.pop("first_absent_at", None) is not None
                elif "first_absent_at" not in entry:
                    entry["first_absent_at"] = _stamp(now)
                    changed = True
                elif now - datetime.fromisoformat(entry["first_absent_at"]) >= ABSENT_TTL:
                    del stored[finding_id]
                    changed = True
            return changed

        self._mutate(apply)
        return self.snapshot()

    def _mutate(self, apply: Callable[[dict[str, Any]], bool]) -> None:
        for attempt in range(_RETRIES):
            if attempt:
                time.sleep(_BACKOFF_S * attempt)
            document = _read_document(self._path)
            base_rev = document["rev"]
            if not apply(document["ids"]):
                return
            document["rev"] = base_rev + 1
            if self._replace(document, base_rev):
                return
        raise StrataError("triage state changed concurrently", hint="retry")

    @property
    def _lock(self) -> Path:
        return self._path.with_name(f"{self._path.name}.lock")

    def _replace(self, document: dict[str, Any], base_rev: int) -> bool:
        """Write `document` beside the store and swap it in, unless the store's `rev` moved past
        `base_rev` meanwhile (False, store untouched). The check and the swap run under the
        write lock. The file is 0600; an interrupted write leaves the previous store untouched."""
        ensure_private_dir(self._path.parent, tighten=self._path.parent == strata_home() / "triage")
        target = check_write_destination(self._path, what="triage store", is_ours=_is_triage_store)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".strata-triage-")
        try:
            if os.name == "posix":
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(document, indent=2, sort_keys=True) + "\n")
            with _exclusive(self._lock):
                if _current_rev(target) != base_rev:
                    Path(tmp).unlink(missing_ok=True)
                    return False
                os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return True


def triage_rows(
    graph: IRGraph, baseline: Mapping[str, set[str]] | None, store: TriageStore
) -> list[TriageRow]:
    """One row per finding id, its status derived here and nowhere else.

    Current ids (in `finding_records` order; a duplicated id is one row, its first record):
    baselined when the id is in `baseline` for its category, which wins over an
    acknowledgement (the ack record is kept and shown); else acknowledged; else new. Then the
    acknowledged or baselined ids no longer found, by (category, id): fixed when their
    category's check ran, not_checked when it did not; never fixed for a category that was not
    checked. Calls `store.observe()`, so absence is stamped as a side effect.
    """
    findings = _Findings.of(graph)
    if findings != store._findings:
        raise ValueError("triage_rows: the store was opened on a different graph")
    stored = store.observe()["ids"]
    acked = {i: e for i, e in stored.items() if "unacked_at" not in e}
    known = baseline or {}

    rows: list[TriageRow] = []
    seen: set[str] = set()
    for record in finding_records(graph):
        finding_id, category = record["id"], record["category"]
        if finding_id in seen:
            continue
        seen.add(finding_id)
        entry = acked.get(finding_id, {})
        status: Status
        if finding_id in known.get(category, ()):
            status = "baselined"
        elif entry:
            status = "acknowledged"
        else:
            status = "new"
        rows.append(
            TriageRow(
                id=finding_id,
                category=category,
                label=record["label"],
                message=record["message"],
                subject_id=record["subject_id"],
                source_file=record["source_file"],
                source_line=record["source_line"],
                status=status,
                acked_at=entry.get("acked_at"),
                note=entry.get("note"),
            )
        )

    absent: dict[tuple[str, str], dict[str, Any]] = {}
    for category, ids in known.items():
        for finding_id in ids - seen:
            absent[(category, finding_id)] = acked.get(finding_id, {})
    for finding_id, entry in acked.items():
        if finding_id not in seen:
            absent.setdefault((entry["category"], finding_id), entry)
    for (category, finding_id), entry in sorted(absent.items()):
        checked = category in findings.checked
        rows.append(
            TriageRow(
                id=finding_id,
                category=category,
                label=finding_id,
                message="no longer found" if checked else f"{category} was not checked this run",
                subject_id=None,
                source_file=None,
                source_line=None,
                status="fixed" if checked else "not_checked",
                acked_at=entry.get("acked_at"),
                note=entry.get("note"),
            )
        )
    return rows
