# Starts the leg's sensor if no live one is heartbeating, and restarts one that is alive but blind. Idempotent; safe every 5 minutes.
# RI-04 (2026-10-23): the sensor is src/duval.py (the Duval loop); src/sensor.py (the named-person sensor, RI-01..03) is retired.
# 2026-10-29: blind means the heartbeat is fresh but no launch has been logged for 10 minutes while the process has run longer than
# that. On 10-28 the engine ran 7 hours with a live heartbeat and a dead resolver (getaddrinfo) and nothing restarted it: a heartbeat
# is not a feed (decisions/2026-10-29-checklist-tape-outage).
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$hb = Join-Path $root "monitor\heartbeat.json"
$log = Join-Path $root "monitor\guard.log"
$blindSeconds = 600
$alive = $false
$blind = $false
$proc = $null
if (Test-Path $hb) {
    $age = ((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds
    if ($age -lt 120) {
        try {
            $h = Get-Content $hb -Raw | ConvertFrom-Json
            $hpid = $h.pid   # never $pid: PowerShell reserves it
            $proc = Get-Process -Id $hpid -ErrorAction Stop
            if ($hpid -and $proc.ProcessName -like "python*") { $alive = $true }
            if ($alive) {
                $up = ((Get-Date) - $proc.StartTime).TotalSeconds
                if ($up -gt $blindSeconds) {
                    if (-not $h.last_launch) { $blind = $true }
                    else {
                        $ll = [DateTime]::Parse($h.last_launch, $null, [System.Globalization.DateTimeStyles]::AdjustToUniversal)
                        if (((Get-Date).ToUniversalTime() - $ll).TotalSeconds -gt $blindSeconds) { $blind = $true }
                    }
                }
            }
        } catch { $alive = $false }
    }
}
if ($alive -and $blind) {
    try { Stop-Process -Id $proc.Id -Force -ErrorAction Stop } catch {}
    Add-Content $log ("{0} engine blind (no launch for over {1} s, heartbeat alive): killed pid {2}" -f (Get-Date -Format o), $blindSeconds, $proc.Id)
    $alive = $false
}
if (-not $alive) {
    New-Item -ItemType Directory -Force (Join-Path $root "monitor") | Out-Null
    $envFile = Join-Path $root ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | Where-Object { $_ -match '^\s*([A-Z_]+)=(.*)$' } | ForEach-Object { [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), "Process") }
    }
    Start-Process -FilePath "python" -ArgumentList @((Join-Path $root "src\duval.py")) -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $root "monitor\sensor-stdout.log") -RedirectStandardError (Join-Path $root "monitor\sensor-stderr.log")
    Add-Content $log ("{0} started sensor" -f (Get-Date -Format o))
}
