"""Run Alembic migrations under a PostgreSQL advisory lock."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from brp.db import create_database_engine

MIGRATION_LOCK_ID = 4_277_001


def main() -> None:
    engine = create_database_engine()
    config = Config("alembic.ini")
    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK_ID})
            try:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            finally:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK_ID}
                )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
