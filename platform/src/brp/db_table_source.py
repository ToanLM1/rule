"""Bounded, read-only PostgreSQL table discovery and Canonical Package mapping."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from decimal import Decimal

import psycopg
from psycopg import sql
from pydantic import Field, model_validator

from brp.canonical_package.models import (
    BusinessScenario,
    CanonicalDecisionPackage,
    DecisionTable,
    DecisionTableRow,
    PackageCondition,
    PackageEvidence,
    VocabularyField,
    VocabularyRole,
)
from brp.ir.models import (
    DbRowReference,
    HitPolicy,
    JsonScalar,
    Operator,
    ProgramContext,
    ProgramKind,
    ScalarType,
    StrictModel,
)
from brp.secrets import resolve_secret

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
CONNECTION_ALIAS = re.compile(r"^[A-Z][A-Z0-9_]*$")


class TableColumn(StrictModel):
    name: str
    database_type: str
    nullable: bool
    ordinal: int


class DiscoveredTable(StrictModel):
    schema_name: str
    table: str
    kind: str
    columns: list[TableColumn]


class TableImportMapping(StrictModel):
    connection_alias: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    schema_name: str
    table: str
    package_id: str
    package_name: str = Field(min_length=1)
    decision_id: str
    decision_name: str = Field(min_length=1)
    condition_columns: list[str] = Field(min_length=1)
    outcome_columns: list[str] = Field(min_length=1)
    primary_key_columns: list[str] = Field(min_length=1)
    max_rows: int = Field(default=100, ge=1, le=500)
    program_id: str = Field(default="DB_RULE_IMPORT", min_length=1)
    program_kind: ProgramKind = ProgramKind.SERVICE
    entry_point: str = Field(default="database-rule-table", min_length=1)
    scenarios: list[BusinessScenario] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_columns(self) -> TableImportMapping:
        _identifier(self.schema_name)
        _identifier(self.table)
        columns = [
            *self.condition_columns,
            *self.outcome_columns,
            *self.primary_key_columns,
        ]
        for column in columns:
            _identifier(column)
        if len(columns) != len(set(columns)):
            overlap = set(self.condition_columns) & set(self.outcome_columns)
            if overlap:
                raise ValueError(
                    f"condition and outcome columns must be distinct: {sorted(overlap)}"
                )
        return self


def discover_tables(connection_alias: str, schema_name: str) -> list[DiscoveredTable]:
    connection_string = _connection_string(connection_alias)
    _identifier(schema_name)
    query = """
        SELECT c.relname, c.relkind, a.attname,
               pg_catalog.format_type(a.atttypid, a.atttypmod),
               NOT a.attnotnull, a.attnum
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname = %s
          AND c.relkind IN ('r', 'v', 'm')
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY c.relname, a.attnum
        LIMIT 2000
    """
    grouped: dict[tuple[str, str], list[TableColumn]] = {}
    with psycopg.connect(connection_string, connect_timeout=5) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '5s'")
        for table, kind, column, database_type, nullable, ordinal in connection.execute(
            query, (schema_name,)
        ):
            grouped.setdefault((str(table), str(kind)), []).append(
                TableColumn(
                    name=str(column),
                    database_type=str(database_type),
                    nullable=bool(nullable),
                    ordinal=int(ordinal),
                )
            )
    kinds = {"r": "TABLE", "v": "VIEW", "m": "MATERIALIZED_VIEW"}
    return [
        DiscoveredTable(
            schema_name=schema_name,
            table=table,
            kind=kinds[kind],
            columns=columns,
        )
        for (table, kind), columns in grouped.items()
    ]


def import_table_package(mapping: TableImportMapping) -> CanonicalDecisionPackage:
    connection_string = _connection_string(mapping.connection_alias)
    requested = list(
        dict.fromkeys(
            [
                *mapping.primary_key_columns,
                *mapping.condition_columns,
                *mapping.outcome_columns,
            ]
        )
    )
    statement = sql.SQL("SELECT {columns} FROM {schema}.{table} ORDER BY {keys} LIMIT %s").format(
        columns=sql.SQL(", ").join(map(sql.Identifier, requested)),
        schema=sql.Identifier(mapping.schema_name),
        table=sql.Identifier(mapping.table),
        keys=sql.SQL(", ").join(map(sql.Identifier, mapping.primary_key_columns)),
    )
    with psycopg.connect(connection_string, connect_timeout=5) as connection:
        connection.execute("SET TRANSACTION READ ONLY")
        connection.execute("SET LOCAL statement_timeout = '5s'")
        cursor = connection.execute(statement, (mapping.max_rows,))
        rows: list[dict[str, JsonScalar]] = [
            {name: _json_value(value) for name, value in zip(requested, values, strict=True)}
            for values in cursor.fetchall()
        ]
    if not rows:
        raise ValueError("selected PostgreSQL table/view contains no mapped rows")
    types = {column: _scalar_type(rows, column) for column in requested}
    snapshot = json.dumps(
        rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    snapshot_hash = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()

    evidence: list[PackageEvidence] = []
    decision_rows: list[DecisionTableRow] = []
    for number, row in enumerate(rows, 1):
        evidence_id = f"db_row_{number:04d}"
        primary_key = {name: row[name] for name in mapping.primary_key_columns}
        evidence.append(
            PackageEvidence(
                evidence_id=evidence_id,
                summary=(
                    f"Read-only snapshot row from "
                    f"{mapping.schema_name}.{mapping.table}"
                ),
                source_reference=DbRowReference(
                    type="DB_ROW",
                    connection_alias=mapping.connection_alias,
                    schema=mapping.schema_name,
                    table=mapping.table,
                    primary_key=primary_key,
                    snapshot_id=snapshot_hash,
                    snapshot_hash=snapshot_hash,
                ),
            )
        )
        decision_rows.append(
            DecisionTableRow(
                row_id=f"ROW_{number:04d}",
                conditions=[
                    PackageCondition(field=name, operator=Operator.EQ, value=row[name])
                    for name in mapping.condition_columns
                ],
                outcomes={name: row[name] for name in mapping.outcome_columns},
                evidence_ids=[evidence_id],
                confidence=1.0,
            )
        )

    vocabulary = [
        VocabularyField(
            key=name,
            label=name.replace("_", " ").title(),
            type=types[name],
            role=VocabularyRole.INPUT,
            source_path=f"{mapping.schema_name}.{mapping.table}.{name}",
        )
        for name in mapping.condition_columns
    ] + [
        VocabularyField(
            key=name,
            label=name.replace("_", " ").title(),
            type=types[name],
            role=VocabularyRole.OUTPUT,
            source_path=f"{mapping.schema_name}.{mapping.table}.{name}",
        )
        for name in mapping.outcome_columns
    ]
    return CanonicalDecisionPackage(
        package_id=mapping.package_id,
        package_name=mapping.package_name,
        profile="CANONICAL_DECISION_PACKAGE_V1",
        schema_version=1,
        program_contexts=[
            ProgramContext(
                program_id=mapping.program_id,
                kind=mapping.program_kind,
                entry_point=mapping.entry_point,
            )
        ],
        vocabulary=vocabulary,
        decisions=[
            DecisionTable(
                decision_id=mapping.decision_id,
                name=mapping.decision_name,
                hit_policy=HitPolicy.UNIQUE,
                input_fields=mapping.condition_columns,
                output_fields=mapping.outcome_columns,
                rows=decision_rows,
                default_outcome={
                    name: _default_value(types[name]) for name in mapping.outcome_columns
                },
            )
        ],
        business_scenarios=mapping.scenarios,
        evidence=evidence,
    )


def _connection_string(alias: str) -> str:
    if not CONNECTION_ALIAS.fullmatch(alias) or alias == "BRP_DATABASE_URL":
        raise ValueError(
            "source connection must be a separate uppercase environment reference"
        )
    value = resolve_secret(alias)
    if value.startswith("postgresql+psycopg://"):
        value = "postgresql://" + value.removeprefix("postgresql+psycopg://")
    if not value.startswith(("postgresql://", "postgres://")):
        raise ValueError("source connection must be a PostgreSQL URL")
    return value


def _identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe PostgreSQL identifier: {value!r}")
    return value


def _json_value(value: object) -> JsonScalar:
    if value is None:
        raise ValueError("null mapped values are not supported")
    if type(value) in {bool, int, float, str}:
        return value  # type: ignore[return-value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    raise ValueError(f"unsupported PostgreSQL value type: {type(value).__name__}")


def _scalar_type(rows: list[dict[str, JsonScalar]], column: str) -> ScalarType:
    values = [row[column] for row in rows]
    if all(type(value) is bool for value in values):
        return ScalarType.BOOLEAN
    if all(type(value) is int for value in values):
        return ScalarType.INTEGER
    if all(type(value) in {int, float} and type(value) is not bool for value in values):
        return ScalarType.DECIMAL
    if all(type(value) is str for value in values):
        if all(_is_iso_date(str(value)) for value in values):
            return ScalarType.DATE
        return ScalarType.STRING
    raise ValueError(f"column has mixed or unsupported values: {column}")


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _default_value(kind: ScalarType) -> bool | int | float | str:
    if kind is ScalarType.BOOLEAN:
        return False
    if kind is ScalarType.INTEGER:
        return 0
    if kind is ScalarType.DECIMAL:
        return 0.0
    if kind is ScalarType.DATE:
        return "1970-01-01"
    return ""
