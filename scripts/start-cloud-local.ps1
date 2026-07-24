param(
    [string]$EnvFile = "",
    [switch]$SkipWorker,
    [switch]$WorkerOnly
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

# Installers update the persistent Windows PATH, but an already-open Codex/PowerShell
# process keeps its old environment. Refresh it without dropping process-local entries.
$pathEntries = @(
    [Environment]::GetEnvironmentVariable('Path', 'Machine'),
    [Environment]::GetEnvironmentVariable('Path', 'User'),
    $env:Path
) -join ';'
$env:Path = (($pathEntries -split ';' | Where-Object { $_ } | Select-Object -Unique) -join ';')

$requiredCommands = @(
    @{ Name = 'uv'; Install = 'https://docs.astral.sh/uv/getting-started/installation/' },
    @{ Name = 'pnpm.cmd'; Install = 'https://pnpm.io/installation' },
    @{ Name = 'git'; Install = 'https://git-scm.com/download/win' },
    @{ Name = 'java'; Install = 'https://aka.ms/download-jdk/microsoft-jdk-17-windows-x64.msi' }
)
foreach ($required in $requiredCommands) {
    if (-not (Get-Command $required.Name -ErrorAction SilentlyContinue)) {
        throw "Missing prerequisite '$($required.Name)'. Install: $($required.Install)"
    }
}
$javaVersion = (& java --version | Select-Object -First 1) -join ''
if ($javaVersion -notmatch '^(?:openjdk|java) 17[.]|version "17[.]') {
    throw "Java 17 is required; detected: $javaVersion. Install: https://aka.ms/download-jdk/microsoft-jdk-17-windows-x64.msi"
}
$env:JAVA_HOME = Split-Path -Parent (Split-Path -Parent (Get-Command java).Source)

if (-not $EnvFile) {
    $EnvFile = Join-Path (Split-Path -Parent $Root) 'rule\.env'
}
$EnvFile = [System.IO.Path]::GetFullPath($EnvFile)
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Environment file not found: $EnvFile"
}

Get-Content -LiteralPath $EnvFile | ForEach-Object {
    if ($_ -match '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        Set-Item -Path "Env:$($matches[1])" -Value $matches[2]
    }
}
$env:BRP_REPOSITORY_ROOT = $Root

$occupied = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object LocalPort -In 8100, 5173
if ($occupied -and -not $WorkerOnly) {
    $ports = ($occupied.LocalPort | Sort-Object -Unique) -join ', '
    throw "Required local ports are already in use: $ports"
}

Set-Location $Root
uv run --project platform python scripts/check-pg.py
if ($LASTEXITCODE -ne 0) { throw 'Cloud PostgreSQL probe failed' }
uv run --project platform python -m alembic -c platform/alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) { throw 'Alembic migration check failed' }

$Logs = Join-Path $Root 'output\runlogs'
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$Uv = (Get-Command uv).Source
$Pnpm = (Get-Command pnpm.cmd).Source
$processes = @()
if (-not $WorkerOnly) {
    $processes += Start-Process -FilePath $Uv -ArgumentList @(
        'run', '--project', 'platform', 'python', '-m', 'uvicorn',
        'brp.api.app:app', '--host', '127.0.0.1', '--port', '8100'
    ) -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs 'api.out.log') -RedirectStandardError (Join-Path $Logs 'api.err.log') -PassThru
}
if (-not $SkipWorker) {
    $processes += Start-Process -FilePath $Uv -ArgumentList @(
        'run', '--project', 'platform', 'python', '-m', 'brp.worker'
    ) -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs 'worker.out.log') -RedirectStandardError (Join-Path $Logs 'worker.err.log') -PassThru
}
if (-not $WorkerOnly) {
    $processes += Start-Process -FilePath $Pnpm -ArgumentList @(
        '--dir', 'ui', 'dev', '--host', '127.0.0.1'
    ) -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs 'ui.out.log') -RedirectStandardError (Join-Path $Logs 'ui.err.log') -PassThru
}

$PidFile = Join-Path $Logs 'local.pids'
if ($WorkerOnly) {
    $processes.Id | Add-Content -Encoding ASCII $PidFile
} else {
    $processes.Id | Set-Content -Encoding ASCII $PidFile
}
Write-Output ("Started PIDs: " + ($processes.Id -join ', '))
Write-Output 'UI: http://127.0.0.1:5173/'
Write-Output "Logs: $Logs"
