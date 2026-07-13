"""Load the deterministic PostgreSQL fixture used by adapter and E2E tests."""

from __future__ import annotations

import argparse
from pathlib import Path

import psycopg

from db_common import configured_database_url, psycopg_url

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "fixtures" / "legacy-enrollment" / "db"
TABLES = ("product_master", "rate_table", "region_eligibility", "occupation_class")


def statements(path: Path) -> list[str]:
    """Return the simple semicolon-delimited fixture statements."""
    return [statement.strip() for statement in path.read_text(encoding="utf-8").split(";") if statement.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop fixture tables before loading")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database_url = configured_database_url()
    with psycopg.connect(psycopg_url(database_url)) as connection:
        if args.reset:
            connection.execute(
                "DROP TABLE IF EXISTS occupation_class, region_eligibility, rate_table, "
                "product_master CASCADE"
            )
        for path in (DB_DIR / "schema.sql", DB_DIR / "seed.sql"):
            for statement in statements(path):
                connection.execute(statement)

        counts: dict[str, int] = {}
        for table in TABLES:
            row = connection.execute(f"SELECT count(*) FROM {table}").fetchone()
            assert row is not None
            counts[table] = row[0]

    print("Fixture loaded: " + ", ".join(f"{table}={count}" for table, count in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
