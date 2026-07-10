"""FastMCP stdio entry point."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from mcp.server.fastmcp import FastMCP

from brp_mcp_db.connector import DatabaseConnector

mcp = FastMCP("brp-read-only-db")


@lru_cache(maxsize=1)
def connector() -> DatabaseConnector:
    return DatabaseConnector(os.environ["BRP_MCP_DATABASE_URL"])


@mcp.tool()
def list_tables() -> list[dict[str, Any]]:
    """List allowlisted base tables."""
    return connector().list_tables()


@mcp.tool()
def capabilities() -> dict[str, object]:
    """Report driver and stored-object support explicitly."""
    return connector().capabilities()


@mcp.tool()
def table_schema(schema: str, table: str) -> list[dict[str, Any]]:
    """Describe columns for one discovered table."""
    return connector().table_schema(schema, table)


@mcp.tool()
def sample_rows(schema: str, table: str, limit: int = 20) -> list[dict[str, Any]]:
    """Read at most 50 rows from one discovered table."""
    return connector().sample_rows(schema, table, limit=limit)


@mcp.tool()
def stored_procedure_source(schema: str, procedure: str) -> str:
    """Read source for one discovered stored procedure."""
    return connector().stored_procedure_source(schema, procedure)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
