# Loads .env (X_BEARER) and runs the daily roster discovery; output appended to monitor/discover.log.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | Where-Object { $_ -match '^\s*([A-Z_]+)=(.*)$' } | ForEach-Object { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), "Process") }
}
Set-Location $root
("{0} " -f (Get-Date -Format o)) + (python ops\discover.py 2>&1 | Out-String) | Add-Content (Join-Path $root "monitor\discover.log")
