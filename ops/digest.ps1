# Daily Rich Foresight run: a background Claude session follows ~/.claude/commands/rich-foresight.md
# (tick, owed lessons, digest, republish the artifact). A background session, not `claude -p`: print mode has no Artifact tool.
# The last line of the session is appended to monitor/digest.log. The digest file is rebuilt locally first, so it exists even if Claude cannot run.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
$log = Join-Path $root "monitor\digest.log"
python ops\digest.py | Out-Null
$tools = @("Artifact", "Read", "Grep", "Bash(python ops/journal.py:*)", "Bash(python ops/digest.py:*)")
$start = (& claude --bg "/rich-foresight" --allowedTools $tools 2>&1 | Out-String)
if ($start -notmatch 'backgrounded\D+([0-9a-f]{8})') { Add-Content $log ("{0} could not start claude: {1}" -f (Get-Date -Format o), $start.Trim()); exit 1 }
$id = $Matches[1]
$text = ""
foreach ($i in 1..60) {   # up to 10 minutes
    Start-Sleep -Seconds 10
    $text = ((& claude logs $id 2>&1 | Out-String) -replace "\x1b\[[0-9;?]*[A-Za-z]", "")
    if ($text -match "lessons written.*publish") { break }   # the one-line reply the command ends with
}
$last = ($text -split "`n" | Where-Object { $_ -match "lessons written.*publish" } | Select-Object -Last 1)
if (-not $last) { $last = "no result line after 10 minutes; session $id left for inspection (claude logs $id)" } else { & claude rm $id 2>&1 | Out-Null }
Add-Content $log ("{0} {1}" -f (Get-Date -Format o), "$last".Trim())
