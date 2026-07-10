"""Read-only, allowlist-driven PostgreSQL introspection."""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

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


class DatabaseConnector:
    """Bounded catalog and row access with no arbitrary SQL surface."""

    def __init__(
        self,
        connection_url: str,
        *,
        schemas: tuple[str, ...] = ("public",),
        max_rows: int = 50,
        statement_timeout_ms: int = 5_000,
        connect: Callable[..., Connection[Any]] = psycopg.connect,
    ) -> None:
        if not connection_url:
            raise ValueError("connection URL is required")
        if max_rows < 1 or max_rows > 50:
            raise InvalidLimit("max_rows must be between 1 and 50")
        self._connection_url = connection_url
        self._schemas = schemas
        self._max_rows = max_rows
        self._statement_timeout_ms = statement_timeout_ms
        self._connect = connect

    @contextmanager
    def _session(self) -> Any:
        # Never log repr(connection_url), connection exceptions, or driver DSNs.
        LOGGER.info("opening read-only database session")
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
        if limit < 1 or limit > self._max_rows:
            raise InvalidLimit(f"limit must be between 1 and {self._max_rows}")
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
