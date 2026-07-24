from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from brp.canonical_package import compile_package
from brp.canonical_package.models import BusinessScenario
from brp.db_table_source import (
    TableImportMapping,
    discover_tables,
    import_table_package,
)


class Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def __iter__(self) -> Iterator[tuple[object, ...]]:
        return iter(self.rows)

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


class Connection:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.statements: list[object] = []

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, statement: object, params: object = None) -> Cursor:
        del params
        self.statements.append(statement)
        if isinstance(statement, str) and statement.startswith("SET"):
            return Cursor([])
        return Cursor(self.rows)


def mapping() -> TableImportMapping:
    return TableImportMapping(
        connection_alias="RULE_SOURCE_URL",
        schema_name="rule_source",
        table="eligibility_rules",
        package_id="db_eligibility",
        package_name="DB Eligibility",
        decision_id="eligibility",
        decision_name="Eligibility",
        condition_columns=["region_code", "min_age"],
        outcome_columns=["eligible"],
        primary_key_columns=["rule_id"],
        scenarios=[
            BusinessScenario(
                scenario_id="adult_seoul",
                name="Adult in Seoul",
                inputs={"region_code": "SEOUL", "min_age": 18},
                expected={"eligible": True},
            )
        ],
    )


def test_discovery_uses_catalog_metadata_and_read_only_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = Connection(
        [
            ("eligibility_rules", "r", "rule_id", "integer", False, 1),
            ("eligibility_rules", "r", "region_code", "text", False, 2),
        ]
    )
    monkeypatch.setenv("RULE_SOURCE_URL", "postgresql://example.invalid/rules")
    monkeypatch.setattr("brp.db_table_source.psycopg.connect", lambda *args, **kwargs: connection)

    tables = discover_tables("RULE_SOURCE_URL", "rule_source")

    assert tables[0].table == "eligibility_rules"
    assert [item.name for item in tables[0].columns] == ["rule_id", "region_code"]
    assert connection.statements[:2] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '5s'",
    ]


def test_mapped_rows_produce_compilable_package_with_db_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = Connection(
        [
            (1, "SEOUL", 18, True),
            (2, "JEJU", 21, False),
        ]
    )
    monkeypatch.setenv("RULE_SOURCE_URL", "postgresql://example.invalid/rules")
    monkeypatch.setattr("brp.db_table_source.psycopg.connect", lambda *args, **kwargs: connection)

    package = import_table_package(mapping())
    result = compile_package(
        package,
        actor="db-importer",
        authored_at=datetime(2026, 7, 23, tzinfo=UTC),
        reason="DB import",
    )

    assert result.valid is True
    assert len(package.decisions[0].rows) == 2
    reference = package.evidence[0].source_reference
    assert reference.type == "DB_ROW"
    assert reference.schema_name == "rule_source"
    assert reference.primary_key == {"rule_id": 1}


@pytest.mark.parametrize(
    "alias,schema",
    [
        ("BRP_DATABASE_URL", "rule_source"),
        ("RULE_SOURCE_URL", "rule_source; DROP TABLE users"),
    ],
)
def test_source_connection_and_identifiers_fail_closed(
    monkeypatch: pytest.MonkeyPatch, alias: str, schema: str
) -> None:
    monkeypatch.setenv("RULE_SOURCE_URL", "postgresql://example.invalid/rules")
    with pytest.raises(ValueError):
        discover_tables(alias, schema)
