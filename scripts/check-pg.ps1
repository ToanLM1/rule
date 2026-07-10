$ErrorActionPreference = 'Stop'

uv run --project platform python scripts/check-pg.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
