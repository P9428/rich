# Starts the leg's sensor if no live one is heartbeating. Idempotent; safe every 5 minutes.
# RI-04 (2026-10-23): the sensor is src/duval.py (the Duval loop); src/sensor.py (the named-person sensor, RI-01..03) is retired.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$hb = Join-Path $root "monitor\heartbeat.json"
$alive = $false
if (Test-Path $hb) {
    $age = ((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds
    if ($age -lt 120) {
        try {
            $hpid = (Get-Content $hb -Raw | ConvertFrom-Json).pid   # never $pid: PowerShell reserves it
            if ($hpid -and (Get-Process -Id $hpid -ErrorAction Stop).ProcessName -like "python*") { $alive = $true }
        } catch { $alive = $false }
    }
}
if (-not $alive) {
    New-Item -ItemType Directory -Force (Join-Path $root "monitor") | Out-Null
    $envFile = Join-Path $root ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | Where-Object { $_ -match '^\s*([A-Z_]+)=(.*)$' } | ForEach-Object { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), "Process") }
    }
    Start-Process -FilePath "python" -ArgumentList @((Join-Path $root "src\duval.py")) -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $root "monitor\sensor-stdout.log") -RedirectStandardError (Join-Path $root "monitor\sensor-stderr.log")
    Add-Content (Join-Path $root "monitor\guard.log") ("{0} started sensor" -f (Get-Date -Format o))
}
