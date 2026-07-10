#!/usr/bin/env bash
set -euo pipefail

uv run --project platform python scripts/load_fixture_db.py "$@"
