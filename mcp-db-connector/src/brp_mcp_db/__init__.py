"""Reusable BRP database MCP connector."""

from brp_mcp_db.connector import (
    DatabaseConnector,
    InvalidIdentifier,
    InvalidLimit,
    PostgresDriver,
    SQLiteDriver,
    UnsupportedCapability,
)

__version__ = "0.1.0"

__all__ = [
    "DatabaseConnector",
    "InvalidIdentifier",
    "InvalidLimit",
    "PostgresDriver",
    "SQLiteDriver",
    "UnsupportedCapability",
]
