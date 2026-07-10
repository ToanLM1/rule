#!/usr/bin/env bash
set -euo pipefail

uv run --project platform python scripts/check-pg.py
