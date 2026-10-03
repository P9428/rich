# Daily Rich Foresight run: an unattended Claude session follows ~/.claude/commands/rich-foresight.md
# (tick, owed lessons, tomorrow's market forecasts, digest, update the Rich Foresight Doc). Print mode, as the hyperliquid
# journal runs: an unattended session has the Claude Docs tools and no Artifact tool, so the page is a Doc.
# The tools are held to the journal's two commands, file reads and the Docs tools; it can change no rule and place no order.
# Everything the session prints is appended to monitor/digest.log. The digest files are rebuilt locally first, so they exist even if Claude cannot run.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
$log = Join-Path $root "monitor\digest.log"
python ops\digest.py | Out-Null
$claude = Join-Path $env:USERPROFILE ".local\bin\claude.exe"
if (-not (Test-Path $claude)) { $claude = "claude" }
$tools = @("Bash(python ops/journal.py:*)", "Bash(python ops/digest.py:*)", "Read", "Grep", "Glob", "ToolSearch",
           "mcp__claude_ai_Claude_Docs__read", "mcp__claude_ai_Claude_Docs__update", "mcp__claude_ai_Claude_Docs__guide")
"=== $(Get-Date -Format o)" | Out-File -FilePath $log -Append -Encoding utf8
& $claude -p "/rich-foresight" --allowedTools $tools 2>&1 | Out-File -FilePath $log -Append -Encoding utf8
