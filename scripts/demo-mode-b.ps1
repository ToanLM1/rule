$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
uv run --project platform python scripts/demo_mode_b.py
exit $LASTEXITCODE
