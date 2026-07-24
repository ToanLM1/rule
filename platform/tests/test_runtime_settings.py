from unittest.mock import patch

from brp.db import create_database_engine
from brp.settings import RuntimeSettings


def test_database_connect_timeout_defaults_to_five_seconds(monkeypatch) -> None:
    monkeypatch.delenv("BRP_DATABASE_CONNECT_TIMEOUT_SECONDS", raising=False)
    assert RuntimeSettings.from_environment().database_connect_timeout_seconds == 5


def test_database_connect_timeout_is_passed_to_psycopg(monkeypatch) -> None:
    monkeypatch.setenv("BRP_DATABASE_CONNECT_TIMEOUT_SECONDS", "7")
    with patch("brp.db.create_engine") as create_engine:
        create_database_engine()
    assert create_engine.call_args.kwargs["connect_args"]["connect_timeout"] == 7
