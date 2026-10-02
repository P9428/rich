# Registers the workstation tasks through ~/ops/run-hidden.vbs (no console pop-ups), same as the sibling repos.
#   rich - SENSOR GUARD : at logon and every 5 minutes, keeps src/sensor.py alive 24/7
#   rich - READOUT      : daily 05:30 local: loss-first gates on the paper journal -> out/readout.txt
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
Get-ScheduledTask -TaskName "rich - *" | ForEach-Object { "{0,-22} {1}" -f $_.TaskName, $_.State }
