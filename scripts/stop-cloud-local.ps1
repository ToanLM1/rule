$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root 'output\runlogs\local.pids'
if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Output 'No local PID file found.'
    exit 0
}
$ids = [System.Collections.Generic.HashSet[int]]::new()
Get-Content -LiteralPath $PidFile | ForEach-Object {
    if ($_ -match '^\d+$') { [void]$ids.Add([int]$_) }
}
# uv/pnpm launchers may exit after spawning Python/Node. ParentProcessId remains usable,
# so collect the complete recorded process trees before stopping their surviving children.
do {
    $added = $false
    Get-CimInstance Win32_Process | ForEach-Object {
        if ($ids.Contains([int]$_.ParentProcessId) -and $ids.Add([int]$_.ProcessId)) {
            $added = $true
        }
    }
} while ($added)
$ids | Sort-Object -Descending | ForEach-Object {
    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue
}
Remove-Item -LiteralPath $PidFile
Write-Output 'Stopped Rule Platform local processes.'
