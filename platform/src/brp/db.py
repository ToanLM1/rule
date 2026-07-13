"""Database engine configuration for the governed repository."""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine

LOCAL_DATABASE_URL = "postgresql+psycopg://brp:brp@localhost:55432/brp"


def database_url() -> str:
    return os.getenv("BRP_DATABASE_URL", LOCAL_DATABASE_URL)


def create_database_engine(*, echo: bool = False) -> Engine:
    return create_engine(database_url(), echo=echo, pool_pre_ping=True)
