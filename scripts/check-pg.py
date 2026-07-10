"""Probe the configured PostgreSQL database without exposing credentials."""

from __future__ import annotations

import os
import sys

import psycopg

LOCAL_DATABASE_URL = "postgresql+psycopg://brp:brp@localhost:55432/brp"


def psycopg_url(value: str) -> str:
    """Convert the SQLAlchemy psycopg URL to a libpq-compatible URL."""
    return value.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> int:
    database_url = os.getenv("BRP_DATABASE_URL", LOCAL_DATABASE_URL)
    try:
        with psycopg.connect(psycopg_url(database_url), connect_timeout=5) as connection:
            version = connection.execute("select current_setting('server_version')").fetchone()
    except psycopg.Error as exc:
        print(f"PostgreSQL probe failed: {exc.__class__.__name__}", file=sys.stderr)
        return 1

    assert version is not None
    print(f"PostgreSQL ready (server {version[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
