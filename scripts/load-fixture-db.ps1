$ErrorActionPreference = 'Stop'

uv run --project platform python scripts/load_fixture_db.py @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
