# Registers the workstation tasks through ~/ops/run-hidden.vbs (no console pop-ups), same as the sibling repos.
#   rich - SENSOR GUARD : at logon and every 5 minutes, keeps src/sensor.py alive 24/7
#   rich - READOUT      : daily 05:30 local: loss-first gates on the paper journal -> out/readout.txt
#   rich - FIVE         : daily 05:50 local: RI-05, the 5 % loop replayed on the tape beside RI-04's control -> out/five.md
#   rich - FORESIGHT    : daily 06:05 local: lessons owed, tomorrow's market forecasts, digest, update the Rich Foresight Doc (ops/digest.ps1)
#   rich - JOURNAL     : every 5 minutes: shadow marks, forecast resolution, out/journal.md (ops/journal.py tick)
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$vbs = Join-Path $env:USERPROFILE "ops\run-hidden.vbs"
$guardArgs = "//B //Nologo `"$vbs`" `"powershell.exe`" -NoProfile -ExecutionPolicy Bypass -File `"$root\ops\sensor_guard.ps1`""
$readArgs = "//B //Nologo `"$vbs`" `"python`" `"$root\ops\readout.py`""
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable
$guardTriggers = @((New-ScheduledTaskTrigger -AtLogOn), (New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5)))
Register-ScheduledTask -TaskName "rich - SENSOR GUARD" -Action (New-ScheduledTaskAction -Execute "wscript.exe" -Argument $guardArgs) -Trigger $guardTriggers -Settings $settings -Force | Out-Null
Register-ScheduledTask -TaskName "rich - READOUT" -Action (New-ScheduledTaskAction -Execute "wscript.exe" -Argument $readArgs -WorkingDirectory $root) -Trigger (New-ScheduledTaskTrigger -Daily -At 05:30) -Settings $settings -Force | Out-Null
$discArgs = "//B //Nologo `"$vbs`" `"powershell.exe`" -NoProfile -ExecutionPolicy Bypass -File `"$root\ops\discover.ps1`""
Register-ScheduledTask -TaskName "rich - DISCOVER" -Action (New-ScheduledTaskAction -Execute "wscript.exe" -Argument $discArgs -WorkingDirectory $root) -Trigger (New-ScheduledTaskTrigger -Daily -At 05:00) -Settings $settings -Force | Out-Null
$jrnArgs = "//B //Nologo `"$vbs`" `"python`" `"$root\ops\journal.py`" tick"
Register-ScheduledTask -TaskName "rich - JOURNAL" -Action (New-ScheduledTaskAction -Execute "wscript.exe" -Argument $jrnArgs -WorkingDirectory $root) -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5)) -Settings $settings -Force | Out-Null
$popArgs = "//B //Nologo `"$vbs`" `"python`" `"$root\ops\population.py`" --days 3"
Register-ScheduledTask -TaskName "rich - POPULATION" -Action (New-ScheduledTaskAction -Execute "wscript.exe" -Argument $popArgs -WorkingDirectory $root) -Trigger (New-ScheduledTaskTrigger -Daily -At 05:45) -Settings $settings -Force | Out-Null
$fiveArgs = "//B //Nologo `"$vbs`" `"python`" `"$root\ops\five_replay.py`" --days 5"
Register-ScheduledTask -TaskName "rich - FIVE" -Action (New-ScheduledTaskAction -Execute "wscript.exe" -Argument $fiveArgs -WorkingDirectory $root) -Trigger (New-ScheduledTaskTrigger -Daily -At 05:50) -Settings $settings -Force | Out-Null
$digArgs = "//B //Nologo `"$vbs`" `"powershell.exe`" -NoProfile -ExecutionPolicy Bypass -File `"$root\ops\digest.ps1`""
Register-ScheduledTask -TaskName "rich - FORESIGHT" -Action (New-ScheduledTaskAction -Execute "wscript.exe" -Argument $digArgs -WorkingDirectory $root) -Trigger (New-ScheduledTaskTrigger -Daily -At 06:05) -Settings $settings -Force | Out-Null
Get-ScheduledTask -TaskName "rich - *" | ForEach-Object { "{0,-22} {1}" -f $_.TaskName, $_.State }
