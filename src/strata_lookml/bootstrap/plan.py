"""Plan-then-apply file writes for `strata bootstrap` / `strata conductor init`.

A command first builds a list of `FileOp`s (pure: reads the tree, writes nothing), then
`apply_plan` performs them. Each write is a temp file + `os.replace`; if any op fails, every
file created in this run is removed and every file overwritten is restored, so a bootstrap
either lands completely or leaves the repo as it found it.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from strata_lookml.errors import StrataError

TEMPLATES = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class FileOp:
    """One planned filesystem effect. `label` is the human word for it (wrote, appended, skip…)."""

    action: Literal["write", "mkdir", "skip"]
    path: Path
    content: str | None = None
    label: str = ""


def render_template(name: str, subs: dict[str, str] | None = None) -> str:
    content = (TEMPLATES / name).read_text(encoding="utf-8")
    for key, value in (subs or {}).items():
        content = content.replace(key, value)
    return content


def plan_template_write(
    dest: Path, template: str, subs: dict[str, str] | None, force: bool, shown: str
) -> FileOp:
    """Write a rendered template, or skip when `dest` exists and `force` is off."""
    if dest.exists() and not force:
        return FileOp("skip", dest, label=f"skip (exists): {shown}")
    return FileOp("write", dest, render_template(template, subs), label=f"wrote: {shown}")


def render_mcp_client_config(
    repo: str | Path,
    usage_fixture: str | Path | None = None,
    schema_fixture: str | Path | None = None,
    client: str = "claude",
) -> str:
    """The one renderer for the MCP client config (`.mcp.json` / `.cursor/mcp.json`).

    Used by `strata bootstrap` and `strata mcp config --client`, so the two cannot drift.
    """
    env = {"STRATA_REPO_PATH": str(repo)}
    if usage_fixture:
        env["STRATA_USAGE_FIXTURE"] = str(usage_fixture)
    if schema_fixture:
        env["STRATA_SCHEMA_FIXTURE"] = str(schema_fixture)
    server: dict[str, object] = {
        "command": str(Path(sys.executable).parent / "strata-mcp"),
        "env": env,
    }
    if client == "cursor":
        server["type"] = "stdio"
    return json.dumps({"mcpServers": {"strata": server}}, indent=2) + "\n"


def _replace(src: str, dst: Path) -> None:
    os.replace(src, dst)


def _write_atomic(path: Path, content: str) -> None:
    tmp = path.with_name(f".{path.name}.strata-tmp-{os.getpid()}")
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        if path.exists():
            os.chmod(tmp, path.stat().st_mode & 0o7777)
        _replace(str(tmp), path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _make_dirs(path: Path, created_dirs: list[Path]) -> None:
    missing: list[Path] = []
    cur = path
    while not cur.exists():
        missing.append(cur)
        cur = cur.parent
    for d in reversed(missing):
        d.mkdir()
        created_dirs.append(d)


def resolve_fixture(path: str | Path | None) -> Path | None:
    """Normalise a fixture path the way every command does: expanded, absolute."""
    return Path(path).expanduser().resolve() if path else None


def apply_plan(ops: Sequence[FileOp]) -> None:
    """Apply `ops` in order; on any failure undo this run's changes and raise `StrataError`.

    Rollback is best effort per step: every restore/unlink is attempted even if an earlier one
    fails, and the raised error says which restores did not work.
    """
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    overwritten: dict[Path, bytes] = {}
    inflight: tuple[Path, bytes | None] | None = None
    try:
        for op in ops:
            if op.action == "skip":
                continue
            if op.action == "mkdir":
                _make_dirs(op.path, created_dirs)
                continue
            assert op.content is not None
            # Write through a symlink: the link stays a link, its target gets the content.
            dest = Path(os.path.realpath(op.path))
            _make_dirs(dest.parent, created_dirs)
            prior = dest.read_bytes() if dest.exists() else None
            inflight = (dest, prior)
            _write_atomic(dest, op.content)
            inflight = None
            # Recorded only once the replace succeeded: a failed write changed nothing.
            if prior is None:
                created_files.append(dest)
            else:
                overwritten[dest] = prior
    except BaseException as exc:  # incl. KeyboardInterrupt: undo, then re-raise it as is
        problems: list[str] = []
        if inflight is not None:
            # The replace may have landed just before the interrupt; undo it only if it did.
            path, prior = inflight
            if prior is None:
                created_files.append(path)
            elif path.exists() and path.read_bytes() != prior:
                overwritten[path] = prior
        for path, data in overwritten.items():
            try:
                path.write_bytes(data)
            except OSError as undo_exc:
                problems.append(f"could not restore {path}: {undo_exc}")
        for path in created_files:
            try:
                path.unlink(missing_ok=True)
            except OSError as undo_exc:
                problems.append(f"could not remove {path}: {undo_exc}")
        for d in reversed(created_dirs):
            with contextlib.suppress(OSError):
                d.rmdir()
        if not isinstance(exc, Exception):
            raise
        message = f"Write failed ({exc})."
        if problems:
            message += " Rollback incomplete: " + "; ".join(problems)
        else:
            message += " Nothing was changed."
        raise StrataError(
            message, hint="Fix the cause (permissions, disk space) and re-run."
        ) from exc


def report_ops(ops: Sequence[FileOp], dry_run: bool = False) -> None:
    """Print one line per op that does something (or says it was skipped)."""
    import click

    for op in ops:
        if op.action == "mkdir":
            continue
        if op.action == "skip":
            click.echo(f"  {op.label}")
        else:
            label = op.label
            if dry_run:
                label = label.replace("wrote:", "would write:").replace(
                    "appended:", "would append:"
                )
            click.secho(f"  {label}", fg=None if dry_run else "green")
