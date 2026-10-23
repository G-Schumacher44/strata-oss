"""L1 usage and cost enrichment data structures."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ExploreUsage:
    model: str
    explore: str
    query_count: int
    last_queried_at: str | None = None

    @property
    def key(self) -> str:
        return f"{self.model}.{self.explore}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContentReference:
    content_id: str
    content_type: str
    model: str
    explore: str
    title: str = ""

    @property
    def explore_key(self) -> str:
        return f"{self.model}.{self.explore}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PDTBuild:
    view: str
    build_count: int
    last_built_at: str | None
    bytes_processed: int
    estimated_cost_usd: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DeadCodeEvidence:
    id: str
    kind: str
    name: str
    source_file: str
    static_reason: str
    usage_reason: str
    evidence_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PDTLedgerRecord:
    view: str
    source_file: str
    build_count: int
    bytes_processed: int
    estimated_cost_usd: float
    used_by_explores: list[str]
    status: str
    evidence_ids: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SchemaTable:
    name: str
    columns: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SchemaDriftRecord:
    id: str
    kind: str
    table: str
    source_file: str
    reason: str
    evidence_ids: list[str]
    column: str | None = None
    field: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
