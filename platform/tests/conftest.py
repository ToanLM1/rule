"""Global test safety fuse for database-backed and destructive suites."""

import pytest

from brp.db import assert_isolated_test_database


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database() -> None:
    assert_isolated_test_database()
