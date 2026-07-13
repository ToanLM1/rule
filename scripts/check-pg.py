"""Probe the configured PostgreSQL database without exposing credentials."""

from __future__ import annotations

import sys

import psycopg

from db_common import configured_database_url, psycopg_url


def main() -> int:
    database_url = configured_database_url()
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
