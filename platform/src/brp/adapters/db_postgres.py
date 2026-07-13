"""Mapping-driven PostgreSQL rule-table adapter."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import yaml
from pydantic import BaseModel, ConfigDict, Field

from brp.adapters.contracts import (
    SOURCE_ADAPTER_CAPABILITY,
    AdapterDiagnostic,
    CandidateDecision,
    ExtractionBatch,
    Source,
    SourceSnapshot,
)
from brp.config.models import SiteProfile
from brp.ir.models import (
    Action,
    Condition,
    ConditionGroup,
    DbRowReference,
    DecisionContent,
    HitPolicy,
    InputDefinition,
    InputOperand,
    LiteralOperand,
    Operator,
    OutputDefinition,
    ProgramContext,
    Rule,
    RuleOrigin,
    ScalarType,
)


class DatabaseReader(Protocol):
    def sample_rows(self, schema: str, table: str, *, limit: int = 20) -> list[dict[str, Any]]: ...


class TableMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    table: str
    decision_key: str
    condition_columns: list[str] = Field(min_length=1)
    action_columns: list[str] = Field(min_length=1)
    schema_name: str = "public"
    primary_key_columns: list[str] | None = None


class MappingSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tables: list[TableMapping] = Field(min_length=1)


class PostgresTableAdapter:
    name = "db-postgres"
    capability_version = SOURCE_ADAPTER_CAPABILITY

    def __init__(self, reader: DatabaseReader, profile: SiteProfile, mapping_path: Path) -> None:
        self.reader = reader
        self.profile = profile
        document = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
        self.mapping = MappingSpec.model_validate(document)

    def discover(self, site_config: object) -> list[Source]:
        del site_config
        return [
            Source(
                source_id=f"db:{mapping.schema_name}.{mapping.table}",
                kind="postgres-table",
                locator={"mapping": mapping.model_dump(mode="json")},
            )
            for mapping in sorted(
                self.mapping.tables, key=lambda item: (item.schema_name, item.table)
            )
        ]

    def extract(self, source: Source) -> ExtractionBatch:
        mapping = TableMapping.model_validate(source.locator["mapping"])
        raw_rows = self.reader.sample_rows(mapping.schema_name, mapping.table, limit=50)
        columns = [*mapping.condition_columns, *mapping.action_columns]
        missing = sorted(
            {column for column in columns if any(column not in row for row in raw_rows)}
        )
        if missing:
            raise ValueError(f"mapped columns missing from {mapping.table}: {missing}")
        key_columns = mapping.primary_key_columns or mapping.condition_columns
        rows = [_normalize_row(row, columns) for row in raw_rows]
        rows.sort(key=lambda row: _sort_key(row, key_columns))
        snapshot_hash = _snapshot_hash(rows)
        content = self._content(mapping, rows, key_columns, snapshot_hash)
        snapshot = SourceSnapshot(
            source_id=source.source_id,
            revision=snapshot_hash,
            content_hash=snapshot_hash,
            captured_at=datetime.now(UTC),
        )
        return ExtractionBatch(
            adapter=self.name,
            decisions=[CandidateDecision(decision_key=mapping.decision_key, content=content)],
            diagnostics=[
                AdapterDiagnostic(
                    level="INFO",
                    code="ROWS_MAPPED",
                    message=f"mapped {len(rows)} rows from {mapping.schema_name}.{mapping.table}",
                )
            ],
            source_snapshot=snapshot,
        )

    def _content(
        self,
        mapping: TableMapping,
        rows: list[dict[str, Any]],
        key_columns: list[str],
        snapshot_hash: str,
    ) -> DecisionContent:
        if not rows:
            raise ValueError(f"mapped table is empty: {mapping.table}")
        types = {
            column: _scalar_type(rows, column)
            for column in [*mapping.condition_columns, *mapping.action_columns]
        }
        context_config = self.profile.source.program_contexts[0]
        context = ProgramContext(
            program_id=context_config.program_id,
            kind=context_config.kind,
            entry_point=f"{context_config.class_name}#{context_config.method}",
        )
        rules: list[Rule] = []
        for index, row in enumerate(rows, 1):
            reference = DbRowReference(
                type="DB_ROW",
                connection_alias=self.profile.source.db.connection_env,
                schema=mapping.schema_name,
                table=mapping.table,
                primary_key={column: row[column] for column in key_columns},
                snapshot_id=snapshot_hash,
                snapshot_hash=snapshot_hash,
            )
            rules.append(
                Rule(
                    rule_id=f"R{index:03d}",
                    when=ConditionGroup(
                        all=[
                            Condition(
                                left=InputOperand(kind="INPUT", name=column),
                                operator=Operator.EQ,
                                right=LiteralOperand(kind="LITERAL", value=row[column]),
                            )
                            for column in mapping.condition_columns
                        ]
                    ),
                    then=[
                        Action(output=column, value=row[column])
                        for column in mapping.action_columns
                    ],
                    origin=RuleOrigin.EXTRACTED,
                    source_references=[reference],
                    confidence=1.0,
                )
            )
        return DecisionContent(
            decision_id=mapping.decision_key,
            decision_name=mapping.decision_key.replace("_", " ").title(),
            profile="RULE_IR_V1",
            schema_version=1,
            program_contexts=[context],
            hit_policy=HitPolicy.UNIQUE,
            inputs=[
                InputDefinition(name=column, type=types[column], source_path=column)
                for column in mapping.condition_columns
            ],
            outputs=[
                OutputDefinition(name=column, type=types[column])
                for column in mapping.action_columns
            ],
            default_output={column: _default(types[column]) for column in mapping.action_columns},
            rules=rules,
        )


def _normalize_row(row: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for column in columns:
        value = row[column]
        if value is None:
            raise ValueError(f"IR v1 does not support null mapped values: {column}")
        normalized[column] = float(value) if isinstance(value, Decimal) else value
    return normalized


def _sort_key(row: dict[str, Any], columns: list[str]) -> tuple[str, ...]:
    return tuple(json.dumps(row[column], ensure_ascii=False, sort_keys=True) for column in columns)


def _snapshot_hash(rows: list[dict[str, Any]]) -> str:
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _scalar_type(rows: list[dict[str, Any]], column: str) -> ScalarType:
    values = [row[column] for row in rows]
    if all(type(value) is bool for value in values):
        return ScalarType.BOOLEAN
    if all(type(value) is int for value in values):
        return ScalarType.INTEGER
    if all(type(value) in {int, float} and type(value) is not bool for value in values):
        return ScalarType.DECIMAL
    if all(type(value) is str for value in values):
        return ScalarType.STRING
    raise ValueError(f"column has mixed or unsupported values: {column}")


def _default(kind: ScalarType) -> bool | int | float | str:
    if kind is ScalarType.BOOLEAN:
        return False
    if kind is ScalarType.INTEGER:
        return 0
    if kind is ScalarType.DECIMAL:
        return 0.0
    if kind is ScalarType.DATE:
        return "1970-01-01"
    return ""
