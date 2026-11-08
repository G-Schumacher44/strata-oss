"""Offline warehouse schema facts and deterministic schema-drift evidence."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from strata_lookml.ir.types import IRGraph
from strata_lookml.l1.types import SchemaDriftRecord, SchemaTable

TABLE_COLUMN_RE = re.compile(r"\$\{TABLE\}\.([A-Za-z_][A-Za-z0-9_]*)")


class SchemaProvider(Protocol):
    def tables(self) -> list[SchemaTable]:
        """Return read-only warehouse table/column facts."""


@dataclass(frozen=True)
class SchemaFacts:
    tables: list[SchemaTable]

    @classmethod
    def from_provider(cls, provider: SchemaProvider) -> SchemaFacts:
        return cls(tables=provider.tables())


class FixtureSchemaProvider:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def tables(self) -> list[SchemaTable]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [_table_from_fact(self.path, item) for item in _tables_list(self.path, data)]


def _bad_shape(path: Path, detail: str) -> Exception:
    # Imported at raise time: errors.py pulls the MCP SDK into the L0 import graph.
    from strata_lookml.errors import InvalidInput

    return InvalidInput(
        f"schema facts {path} are malformed: {detail}",
        hint='expected {"tables": [{"name": "<table>", "columns": ["<column>", ...]}]}',
    )


def _tables_list(path: Path, data: object) -> list[object]:
    tables = data.get("tables", []) if isinstance(data, dict) else None
    if not isinstance(tables, list):
        raise _bad_shape(path, '"tables" must be a list')
    return tables


def _table_from_fact(path: Path, item: object) -> SchemaTable:
    if not isinstance(item, dict) or not isinstance(item.get("name"), str):
        raise _bad_shape(path, 'each table needs a string "name"')
    columns = item.get("columns", [])
    if not isinstance(columns, list) or not all(isinstance(c, str) for c in columns):
        raise _bad_shape(path, f'columns of "{item["name"]}" must be a list of column-name strings')
    return SchemaTable(name=item["name"], columns=list(columns))


def load_schema_facts(path: str | Path) -> SchemaFacts:
    return SchemaFacts.from_provider(FixtureSchemaProvider(path))


def enrich_schema_drift(graph: IRGraph, schema_facts: SchemaFacts | None = None) -> IRGraph:
    facts = schema_facts or SchemaFacts(tables=[])
    l1 = graph.metadata.setdefault("l1", {})
    if "schema_drift" in l1:
        raise RuntimeError("enrich_schema_drift called twice on the same graph")

    columns_by_table = {table.name: set(table.columns) for table in facts.tables}
    l1["schema_tables"] = {table.name: table.to_dict() for table in facts.tables}
    l1["schema_drift"] = [item.to_dict() for item in _schema_drift(graph, columns_by_table)]
    return graph


def _schema_drift(graph: IRGraph, columns_by_table: dict[str, set[str]]) -> list[SchemaDriftRecord]:
    records: list[SchemaDriftRecord] = []

    for table in graph.nodes_by_kind("physical_table"):
        if table.name not in columns_by_table:
            records.append(
                SchemaDriftRecord(
                    id=f"schema:missing_table:{table.name}",
                    kind="missing_table",
                    table=table.name,
                    source_file=table.source_file,
                    reason="physical table referenced by resolved IR is absent from schema facts",
                    evidence_ids=[table.id, f"schema_table:{table.name}"],
                )
            )

    table_by_view = _physical_table_by_view(graph)
    for field in graph.nodes_by_kind("field"):
        view = field.attrs.get("view")
        if not isinstance(view, str):
            continue
        physical_table = table_by_view.get(view)
        if not physical_table or physical_table not in columns_by_table:
            continue
        referenced_columns = _table_columns(field.attrs.get("sql", ""))
        for column in referenced_columns:
            if column in columns_by_table[physical_table]:
                continue
            records.append(
                SchemaDriftRecord(
                    id=f"schema:missing_column:{physical_table}.{column}:{field.name}",
                    kind="missing_column",
                    table=physical_table,
                    column=column,
                    field=field.name,
                    source_file=field.source_file,
                    reason="field SQL references a column absent from schema facts",
                    evidence_ids=[field.id, f"schema_table:{physical_table}"],
                )
            )

    return sorted(records, key=lambda item: item.id)


def _physical_table_by_view(graph: IRGraph) -> dict[str, str]:
    result: dict[str, str] = {}
    for edge in graph.edges:
        if edge.relation != "view→physical_table":
            continue
        view = graph.get_node(edge.source)
        table = graph.get_node(edge.target)
        if view and table:
            result[view.name] = table.name
    return result


def _table_columns(sql: str) -> list[str]:
    return sorted(set(TABLE_COLUMN_RE.findall(sql)))
