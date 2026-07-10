import logging
import os

import psycopg
import pytest

from brp_mcp_db import DatabaseConnector, InvalidIdentifier, InvalidLimit

URL = os.getenv("BRP_PSQL_URL", "postgresql://brp:brp@localhost:55432/brp")


@pytest.fixture(scope="module")
def connector() -> DatabaseConnector:
    try:
        with psycopg.connect(URL) as connection:
            connection.execute("SELECT 1")
    except psycopg.OperationalError:
        pytest.skip("local PostgreSQL fixture is unavailable")
    return DatabaseConnector(URL)


def test_catalog_schema_and_bounded_reads(connector: DatabaseConnector) -> None:
    tables = connector.list_tables()
    assert {row["table"] for row in tables} >= {"rate_table", "region_eligibility"}
    assert {row["name"] for row in connector.table_schema("public", "rate_table")} >= {
        "product_code",
        "smoker",
    }
    assert 0 < len(connector.sample_rows("public", "rate_table", limit=2)) <= 2


def test_injection_identifiers_and_excessive_limits_fail(connector: DatabaseConnector) -> None:
    with pytest.raises(InvalidIdentifier):
        connector.sample_rows("public", "rate_table; DROP TABLE rate_table")
    with pytest.raises(InvalidIdentifier):
        connector.table_schema("public; SELECT 1", "rate_table")
    with pytest.raises(InvalidLimit):
        connector.sample_rows("public", "rate_table", limit=51)


def test_transaction_is_read_only_even_with_privileged_local_role(
    connector: DatabaseConnector,
) -> None:
    with (
        pytest.raises(psycopg.errors.ReadOnlySqlTransaction),
        connector._session() as connection,
    ):
        connection.execute("CREATE TABLE connector_must_not_write(id integer)")


def test_secret_is_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    secret = "never-log-this-password"
    broken = DatabaseConnector(f"postgresql://user:{secret}@127.0.0.1:1/missing?connect_timeout=1")
    with caplog.at_level(logging.INFO), pytest.raises(psycopg.OperationalError):
        broken.list_tables()
    assert secret not in caplog.text
