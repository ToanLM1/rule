import logging
import os
import sqlite3
from pathlib import Path

import psycopg
import pytest

from brp_mcp_db import (
    DatabaseConnector,
    InvalidIdentifier,
    InvalidLimit,
    PostgresDriver,
    SQLiteDriver,
    UnsupportedCapability,
)

URL = os.getenv("BRP_PSQL_URL", "postgresql://brp:brp@localhost:55432/brp")


@pytest.fixture(params=["sqlite", "postgresql"])
def connector(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[DatabaseConnector, str]:
    if request.param == "postgresql":
        try:
            with psycopg.connect(URL) as connection:
                connection.execute("SELECT 1")
        except psycopg.OperationalError:
            pytest.skip("local PostgreSQL fixture is unavailable")
        return DatabaseConnector(URL), "public"

    path = tmp_path / "휴대용-규칙.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE rate_table (
                product_code TEXT NOT NULL,
                smoker INTEGER NOT NULL,
                rate REAL NOT NULL
            );
            CREATE TABLE region_eligibility (
                region_code TEXT NOT NULL,
                eligible INTEGER NOT NULL,
                name TEXT NOT NULL
            );
            INSERT INTO rate_table VALUES ('CANCER_BASIC', 0, 1.25);
            INSERT INTO region_eligibility VALUES ('SEOUL', 1, '서울');
            """
        )
    return DatabaseConnector(path.as_uri().replace("file:", "sqlite:")), "main"


def test_shared_catalog_schema_and_bounded_reads(
    connector: tuple[DatabaseConnector, str],
) -> None:
    database, schema = connector
    tables = database.list_tables()
    assert {row["table"] for row in tables} >= {"rate_table", "region_eligibility"}
    assert {row["name"] for row in database.table_schema(schema, "rate_table")} >= {
        "product_code",
        "smoker",
    }
    assert 0 < len(database.sample_rows(schema, "rate_table", limit=2)) <= 2


def test_shared_injection_identifiers_and_excessive_limits_fail(
    connector: tuple[DatabaseConnector, str],
) -> None:
    database, schema = connector
    with pytest.raises(InvalidIdentifier):
        database.sample_rows(schema, "rate_table; DROP TABLE rate_table")
    with pytest.raises(InvalidIdentifier):
        database.table_schema(f"{schema}; SELECT 1", "rate_table")
    with pytest.raises(InvalidLimit):
        database.sample_rows(schema, "rate_table", limit=51)


def test_shared_driver_session_rejects_writes(
    connector: tuple[DatabaseConnector, str],
) -> None:
    database, _ = connector
    driver = database.driver
    if isinstance(driver, PostgresDriver):
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction), driver._session() as connection:
            connection.execute("CREATE TABLE connector_must_not_write(id integer)")
    else:
        assert isinstance(driver, SQLiteDriver)
        with (
            pytest.raises(sqlite3.OperationalError, match="readonly"),
            driver._session() as connection,
        ):
            connection.execute("CREATE TABLE connector_must_not_write(id integer)")


def test_capability_reporting_is_explicit(
    connector: tuple[DatabaseConnector, str],
) -> None:
    database, schema = connector
    capability = database.capabilities()["storedProcedureSource"]
    assert isinstance(capability, dict)
    if database.capabilities()["driver"] == "sqlite":
        assert capability["supported"] is False
        with pytest.raises(UnsupportedCapability, match="no stored-procedure"):
            database.stored_procedure_source(schema, "anything")
    else:
        assert capability["supported"] is True


def test_secret_is_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    secret = "never-log-this-password"
    broken = DatabaseConnector(f"postgresql://user:{secret}@127.0.0.1:1/missing?connect_timeout=1")
    with caplog.at_level(logging.INFO), pytest.raises(psycopg.OperationalError):
        broken.list_tables()
    assert secret not in caplog.text
