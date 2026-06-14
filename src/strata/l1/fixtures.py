"""Fixture-backed L1 facts for deterministic offline enrichment."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

from strata.l1.provider import UsageFacts
from strata.l1.types import ContentReference, ExploreUsage, PDTBuild


def _coerce(cls: type, item: dict[str, Any]) -> Any:
    known = {f.name for f in dataclasses.fields(cls)}
    return cls(**{k: v for k, v in item.items() if k in known})


def load_usage_facts(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    facts: dict[str, Any] = load_usage_facts_collection(path).to_mapping()
    if "period" in raw:
        facts["period"] = raw["period"]
    return facts


def load_usage_facts_collection(path: str | Path) -> UsageFacts:
    return UsageFacts.from_provider(FixtureUsageProvider(path))


class FixtureUsageProvider:
    """Provider for normalized Strata L1 fixture facts."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, Any] | None = None

    def explore_usage(self) -> list[ExploreUsage]:
        data = self._load()
        return [_coerce(ExploreUsage, item) for item in data.get("explore_usage", [])]

    def content_references(self) -> list[ContentReference]:
        data = self._load()
        return [_coerce(ContentReference, item) for item in data.get("content_references", [])]

    def pdt_builds(self) -> list[PDTBuild]:
        data = self._load()
        return [_coerce(PDTBuild, item) for item in data.get("pdt_builds", [])]

    def _load(self) -> dict[str, Any]:
        if self._data is None:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        return self._data
