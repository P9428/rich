# Keeps the academy loop (ops/academy.py --loop) alive: the trader in the bedroom, every 15 minutes, all day. Idempotent; safe every
# 10 minutes from the task "rich - ACADEMY". The loop's heartbeat is monitor/academy.json; a heartbeat older than 40 minutes (two
# missed ticks and a slow record rebuild) means the loop is dead and it is started again. Observation only: it places no order.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$hb = Join-Path $root "monitor\academy.json"
$log = Join-Path $root "monitor\academy-guard.log"
$alive = $false
if (Test-Path $hb) {
    $age = ((Get-Date) - (Get-Item $hb).LastWriteTime).TotalSeconds
    if ($age -lt 2400) {
        try {
            $h = Get-Content $hb -Raw | ConvertFrom-Json
            $hpid = $h.pid
            $proc = Get-Process -Id $hpid -ErrorAction Stop
            if ($hpid -and $proc.ProcessName -like "python*") { $alive = $true }
        } catch { $alive = $false }
    }
}
if (-not $alive) {
    New-Item -ItemType Directory -Force (Join-Path $root "monitor") | Out-Null
    Start-Process -FilePath "python" -ArgumentList @((Join-Path $root "ops\academy.py"), "--loop", "--every", "900") -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $root "monitor\academy-stdout.log") -RedirectStandardError (Join-Path $root "monitor\academy-stderr.log")
    Add-Content $log ("{0} started the academy loop" -f (Get-Date -Format o))
}
