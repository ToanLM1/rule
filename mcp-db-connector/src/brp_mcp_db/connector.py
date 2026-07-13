"""Portable read-only, allowlist-driven database introspection."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

import psycopg
from psycopg import Connection, sql
from psycopg.rows import dict_row

LOGGER = logging.getLogger("brp_mcp_db")


class ConnectorError(ValueError):
    pass


class InvalidIdentifier(ConnectorError):
    pass


class InvalidLimit(ConnectorError):
    pass


class UnsupportedCapability(ConnectorError):
    pass


class DatabaseDriver(Protocol):
    def capabilities(self) -> dict[str, object]: ...

    def list_tables(self) -> list[dict[str, Any]]: ...

    def table_schema(self, schema: str, table: str) -> list[dict[str, Any]]: ...

    def sample_rows(self, schema: str, table: str, *, limit: int) -> list[dict[str, Any]]: ...

    def stored_procedure_source(self, schema: str, procedure: str) -> str: ...


class DatabaseConnector:
    """Stable bounded API delegating to a database-specific read-only driver."""

    def __init__(
        self,
        connection_url: str,
        *,
        schemas: tuple[str, ...] | None = None,
        max_rows: int = 50,
        statement_timeout_ms: int = 5_000,
        connect: Callable[..., Connection[Any]] = psycopg.connect,
    ) -> None:
        if not connection_url:
            raise ValueError("connection URL is required")
        _validate_max_rows(max_rows)
        if connection_url.startswith("sqlite:"):
            self.driver: DatabaseDriver = SQLiteDriver(
                _sqlite_path(connection_url),
                schemas=schemas or ("main",),
                max_rows=max_rows,
                statement_timeout_ms=statement_timeout_ms,
            )
        elif connection_url.startswith(("postgresql://", "postgres://")):
            self.driver = PostgresDriver(
                connection_url,
                schemas=schemas or ("public",),
                max_rows=max_rows,
                statement_timeout_ms=statement_timeout_ms,
                connect=connect,
            )
        else:
            raise ValueError("supported URLs are postgresql://, postgres://, and sqlite://")

    def capabilities(self) -> dict[str, object]:
        return self.driver.capabilities()

    def list_tables(self) -> list[dict[str, Any]]:
        return self.driver.list_tables()

    def table_schema(self, schema: str, table: str) -> list[dict[str, Any]]:
        return self.driver.table_schema(schema, table)

    def sample_rows(self, schema: str, table: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.driver.sample_rows(schema, table, limit=limit)

    def stored_procedure_source(self, schema: str, procedure: str) -> str:
        return self.driver.stored_procedure_source(schema, procedure)


class PostgresDriver:
    name = "postgresql"

    def __init__(
        self,
        connection_url: str,
        *,
        schemas: tuple[str, ...],
        max_rows: int,
        statement_timeout_ms: int,
        connect: Callable[..., Connection[Any]] = psycopg.connect,
    ) -> None:
        self._connection_url = connection_url
        self._schemas = schemas
        self._max_rows = max_rows
        self._statement_timeout_ms = statement_timeout_ms
        self._connect = connect

    def capabilities(self) -> dict[str, object]:
        return {
            "driver": self.name,
            "readOnly": True,
            "storedProcedureSource": {"supported": True},
        }

    @contextmanager
    def _session(self) -> Iterator[Connection[Any]]:
        LOGGER.info("opening read-only postgresql session")
        connection = self._connect(self._connection_url, row_factory=dict_row)
        try:
            with connection.transaction():
                connection.execute("SET TRANSACTION READ ONLY")
                connection.execute(
                    sql.SQL("SET LOCAL statement_timeout = {}").format(
                        sql.Literal(self._statement_timeout_ms)
                    )
                )
                yield connection
        except Exception:
            LOGGER.warning("database operation failed", exc_info=False)
            raise
        finally:
            connection.close()

    def list_tables(self) -> list[dict[str, Any]]:
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT table_schema AS schema, table_name AS table
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE' AND table_schema = ANY(%s)
                ORDER BY table_schema, table_name
                """,
                (list(self._schemas),),
            ).fetchall()
            return [dict(row) for row in rows]

    def table_schema(self, schema: str, table: str) -> list[dict[str, Any]]:
        self._require_table(schema, table)
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT column_name AS name, data_type AS type, is_nullable = 'YES' AS nullable,
                       ordinal_position AS position
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, table),
            ).fetchall()
            return [dict(row) for row in rows]

    def sample_rows(self, schema: str, table: str, *, limit: int = 20) -> list[dict[str, Any]]:
        _validate_limit(limit, self._max_rows)
        self._require_table(schema, table)
        statement = sql.SQL("SELECT * FROM {}.{} LIMIT {}").format(
            sql.Identifier(schema), sql.Identifier(table), sql.Literal(limit)
        )
        with self._session() as connection:
            return [dict(row) for row in connection.execute(statement).fetchall()]

    def stored_procedure_source(self, schema: str, procedure: str) -> str:
        self._require_schema(schema)
        if procedure not in self._procedure_allowlist(schema):
            raise InvalidIdentifier("procedure is not in the discovered catalog allowlist")
        with self._session() as connection:
            row = connection.execute(
                """
                SELECT pg_get_functiondef(p.oid) AS source
                FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = %s AND p.proname = %s
                ORDER BY p.oid LIMIT 1
                """,
                (schema, procedure),
            ).fetchone()
            if row is None:
                raise InvalidIdentifier("procedure disappeared from catalog")
            return str(row["source"])

    def _require_schema(self, schema: str) -> None:
        if schema not in self._schemas:
            raise InvalidIdentifier("schema is not allowlisted")

    def _require_table(self, schema: str, table: str) -> None:
        self._require_schema(schema)
        if (schema, table) not in {(row["schema"], row["table"]) for row in self.list_tables()}:
            raise InvalidIdentifier("table is not in the discovered catalog allowlist")

    def _procedure_allowlist(self, schema: str) -> set[str]:
        with self._session() as connection:
            rows = connection.execute(
                """SELECT p.proname AS name FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = %s""",
                (schema,),
            ).fetchall()
            return {str(row["name"]) for row in rows}


class SQLiteDriver:
    name = "sqlite"

    def __init__(
        self,
        path: Path,
        *,
        schemas: tuple[str, ...],
        max_rows: int,
        statement_timeout_ms: int,
    ) -> None:
        self._path = path.resolve()
        self._schemas = schemas
        self._max_rows = max_rows
        self._timeout_seconds = statement_timeout_ms / 1_000

    def capabilities(self) -> dict[str, object]:
        return {
            "driver": self.name,
            "readOnly": True,
            "storedProcedureSource": {
                "supported": False,
                "reason": "SQLite has no stored-procedure catalog",
            },
        }

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        LOGGER.info("opening read-only sqlite session")
        uri = f"file:{self._path.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=self._timeout_seconds)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA query_only = ON")
            yield connection
        except Exception:
            LOGGER.warning("database operation failed", exc_info=False)
            raise
        finally:
            connection.close()

    def list_tables(self) -> list[dict[str, Any]]:
        self._require_schema("main")
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT 'main' AS schema, name AS 'table'
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def table_schema(self, schema: str, table: str) -> list[dict[str, Any]]:
        self._require_table(schema, table)
        with self._session() as connection:
            rows = connection.execute(f"PRAGMA table_info({_quote_sqlite(table)})").fetchall()
            return [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "nullable": not bool(row["notnull"]),
                    "position": int(row["cid"]) + 1,
                }
                for row in rows
            ]

    def sample_rows(self, schema: str, table: str, *, limit: int = 20) -> list[dict[str, Any]]:
        _validate_limit(limit, self._max_rows)
        self._require_table(schema, table)
        statement = f"SELECT * FROM {_quote_sqlite(table)} LIMIT ?"
        with self._session() as connection:
            return [dict(row) for row in connection.execute(statement, (limit,)).fetchall()]

    def stored_procedure_source(self, schema: str, procedure: str) -> str:
        del procedure
        self._require_schema(schema)
        raise UnsupportedCapability("SQLite has no stored-procedure source capability")

    def _require_schema(self, schema: str) -> None:
        if schema not in self._schemas or schema != "main":
            raise InvalidIdentifier("schema is not allowlisted")

    def _require_table(self, schema: str, table: str) -> None:
        self._require_schema(schema)
        if (schema, table) not in {(row["schema"], row["table"]) for row in self.list_tables()}:
            raise InvalidIdentifier("table is not in the discovered catalog allowlist")


def _sqlite_path(connection_url: str) -> Path:
    parsed = urlparse(connection_url)
    if parsed.netloc not in {"", "localhost"}:
        raise ValueError("SQLite URL must reference a local file")
    path = unquote(parsed.path)
    if len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    if not path or path == "/:memory:":
        raise ValueError("SQLite connector requires an existing file, not memory")
    return Path(path)


def _quote_sqlite(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _validate_max_rows(max_rows: int) -> None:
    if max_rows < 1 or max_rows > 50:
        raise InvalidLimit("max_rows must be between 1 and 50")


def _validate_limit(limit: int, max_rows: int) -> None:
    if limit < 1 or limit > max_rows:
        raise InvalidLimit(f"limit must be between 1 and {max_rows}")
