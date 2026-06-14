"""Replay provider for sanitized Looker/System Activity-shaped rows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strata.l1.types import ContentReference, ExploreUsage, PDTBuild


class ReplayLookerUsageProvider:
    """Map raw-ish sanitized replay rows into normalized L1 facts."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, Any] | None = None

    def explore_usage(self) -> list[ExploreUsage]:
        rows = self._load().get("query_history_rows", [])
        by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            model = _required(row, "model")
            explore = _required(row, "explore")
            key = (model, explore)
            current = by_key.setdefault(key, {"query_count": 0, "last_queried_at": None})
            current["query_count"] += _int(row.get("query_count", 1))
            current["last_queried_at"] = _latest_iso(
                current["last_queried_at"], row.get("created_at")
            )
        return [
            ExploreUsage(
                model=model,
                explore=explore,
                query_count=data["query_count"],
                last_queried_at=data["last_queried_at"],
            )
            for (model, explore), data in sorted(by_key.items())
        ]

    def content_references(self) -> list[ContentReference]:
        rows = self._load().get("content_usage_rows", [])
        refs: list[ContentReference] = []
        for row in rows:
            refs.append(
                ContentReference(
                    content_id=str(_required(row, "content_id")),
                    content_type=str(row.get("content_type", "unknown")),
                    model=_required(row, "model"),
                    explore=_required(row, "explore"),
                    title=str(row.get("title", "")),
                )
            )
        return sorted(refs, key=lambda item: (item.model, item.explore, item.content_id))

    def pdt_builds(self) -> list[PDTBuild]:
        rows = self._load().get("pdt_build_rows", [])
        by_view: dict[str, dict[str, Any]] = {}
        for row in rows:
            view = _required(row, "view")
            current = by_view.setdefault(
                view,
                {
                    "build_count": 0,
                    "last_built_at": None,
                    "bytes_processed": 0,
                    "estimated_cost_usd": 0.0,
                },
            )
            current["build_count"] += _int(row.get("build_count", 1))
            current["last_built_at"] = _latest_iso(current["last_built_at"], row.get("built_at"))
            current["bytes_processed"] += _int(row.get("bytes_processed", 0))
            current["estimated_cost_usd"] += _float(row.get("estimated_cost_usd", 0.0))
        return [
            PDTBuild(
                view=view,
                build_count=data["build_count"],
                last_built_at=data["last_built_at"],
                bytes_processed=data["bytes_processed"],
                estimated_cost_usd=round(data["estimated_cost_usd"], 6),
            )
            for view, data in sorted(by_view.items())
        ]

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        return self._data


def _required(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if value in {None, ""}:
        raise ValueError(f"replay row missing required field: {key}")
    return str(value)


def _int(value: Any) -> int:
    if value in {None, ""}:
        return 0
    return int(value)


def _float(value: Any) -> float:
    if value in {None, ""}:
        return 0.0
    return float(value)


def _latest_iso(current: str | None, candidate: Any) -> str | None:
    if not candidate:
        return current
    candidate_str = str(candidate)
    if current is None or candidate_str > current:
        return candidate_str
    return current
