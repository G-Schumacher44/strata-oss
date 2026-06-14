"""L1 usage provider protocol and normalized fact helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from strata.l1.types import ContentReference, ExploreUsage, PDTBuild


class UsageProvider(Protocol):
    """Offline-safe provider boundary for L1 facts."""

    def explore_usage(self) -> list[ExploreUsage]: ...

    def content_references(self) -> list[ContentReference]: ...

    def pdt_builds(self) -> list[PDTBuild]: ...


@dataclass(frozen=True)
class UsageFacts:
    explore_usage: list[ExploreUsage]
    content_references: list[ContentReference]
    pdt_builds: list[PDTBuild]

    @classmethod
    def from_provider(cls, provider: UsageProvider) -> UsageFacts:
        return cls(
            explore_usage=provider.explore_usage(),
            content_references=provider.content_references(),
            pdt_builds=provider.pdt_builds(),
        )

    def to_mapping(self) -> dict[str, list]:
        return {
            "explore_usage": self.explore_usage,
            "content_references": self.content_references,
            "pdt_builds": self.pdt_builds,
        }
