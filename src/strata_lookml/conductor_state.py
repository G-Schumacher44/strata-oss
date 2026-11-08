"""One parser for conductor state, shared by `strata conductor status` and MCP."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Line-anchored on purpose: prose that merely mentions "active slice" is not state.
_ACTIVE_SLICE = re.compile(r"^[ \t]*(?:[-*][ \t]+)?Active slice:[ \t]*(.+)$", re.IGNORECASE | re.M)


def _active_slice(index_text: str) -> str | None:
    m = _ACTIVE_SLICE.search(index_text)
    if not m:
        return None
    # The value may be annotated ("path.md (review — PR open)") or backticked: first token only.
    value = m.group(1).split()[0].strip("`") if m.group(1).strip() else ""
    return None if not value or value.lower().startswith("none") else value


def _slice_file(conductor_dir: Path, active: str) -> Path | None:
    rel = active.removeprefix("conductor/")
    for candidate in (conductor_dir / rel, conductor_dir / f"{rel}.md"):
        if candidate.is_file():
            return candidate
    return None


def read_status(conductor_dir: str | Path) -> dict[str, Any]:
    """Return active_slice, title, status, mode, next_steps, latest_handoff.

    Every key is always present; unknown values are None. `active_slice` is None unless
    index.md has a line-anchored `Active slice: <path>` that is not `none`.
    """
    conductor_dir = Path(conductor_dir)
    result: dict[str, Any] = {
        "active_slice": None,
        "title": None,
        "status": None,
        "mode": None,
        "next_steps": None,
        "latest_handoff": None,
    }

    index_path = conductor_dir / "index.md"
    if index_path.exists():
        result["active_slice"] = _active_slice(index_path.read_text(encoding="utf-8"))

    active = result["active_slice"]
    slice_path = _slice_file(conductor_dir, active) if active else None
    if slice_path:
        lines = slice_path.read_text(encoding="utf-8").splitlines()
        result["title"] = lines[0].lstrip("# ").strip() if lines else slice_path.name
        result["status"] = next(
            (ln.split(":", 1)[1].strip() for ln in lines if ln.startswith("Status:")), None
        )
        mode_line = next((ln for ln in lines if "conductor_mode:" in ln), None)
        result["mode"] = mode_line.split(":", 1)[1].strip() if mode_line else None

    handoff_path = conductor_dir / "handoff-log.md"
    if handoff_path.exists():
        content = handoff_path.read_text(encoding="utf-8")
        # Split on block headers — the most recent block is first.
        blocks = re.split(r"(?=^## Date:)", content, flags=re.MULTILINE)
        latest = next((b.strip() for b in blocks if b.strip().startswith("## Date:")), "")
        if latest:
            m = re.search(r"Exact Next Steps:\s*(.+?)(?:\n\n|$)", latest, re.DOTALL)
            if m:
                result["next_steps"] = m.group(1).strip()[:500]
            result["latest_handoff"] = "\n".join(latest.splitlines()[:20])
    return result
