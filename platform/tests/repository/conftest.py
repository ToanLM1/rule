from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from brp.db import create_database_engine

PLATFORM = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    configuration = Config(PLATFORM / "alembic.ini")
    command.upgrade(configuration, "head")
    yield


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_database_engine()
    with Session(engine) as database_session:
        yield database_session
        database_session.rollback()
    engine.dispose()
