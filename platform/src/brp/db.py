"""Database engine configuration for the governed repository."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine

from brp.settings import RuntimeSettings

LOCAL_DATABASE_URL = "postgresql+psycopg://brp:brp@localhost:55432/brp"


def database_url() -> str:
    return os.getenv("BRP_DATABASE_URL", LOCAL_DATABASE_URL)


def create_database_engine(*, echo: bool = False) -> Engine:
    settings = RuntimeSettings.from_environment()
    return create_engine(
        database_url(),
        echo=echo,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        connect_args={"options": f"-c statement_timeout={settings.database_statement_timeout_ms}"},
    )


def assert_isolated_test_database() -> None:
    """Refuse destructive tests against a shared application database."""
    value = database_url().split("?", 1)[0].rstrip("/")
    database_name = value.rsplit("/", 1)[-1]
    explicit = os.getenv("BRP_ALLOW_DESTRUCTIVE_TEST_DATABASE", "").lower() == "true"
    if not database_name.endswith("_test") and not explicit:
        raise RuntimeError("destructive tests require a *_test database or explicit isolation flag")
