"""Shared database URL helpers for repository scripts."""

from __future__ import annotations

import os

LOCAL_DATABASE_URL = "postgresql+psycopg://brp:brp@localhost:55432/brp"


def configured_database_url() -> str:
    """Return the application URL with a safe local default."""
    return os.getenv("BRP_DATABASE_URL", LOCAL_DATABASE_URL)


def psycopg_url(value: str) -> str:
    """Convert the SQLAlchemy psycopg URL to a libpq-compatible URL."""
    return value.replace("postgresql+psycopg://", "postgresql://", 1)
