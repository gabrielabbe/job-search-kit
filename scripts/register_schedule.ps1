# Creates three daily Task Scheduler runs (07:00, 13:00, 19:00 local time).
$script = Join-Path $PSScriptRoot "run_scan.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$triggers = "07:00","13:00","19:00" | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
Register-ScheduledTask -TaskName "JobSearch-Scan" -Action $action -Trigger $triggers -Description "Scan job feeds and draft resumes 3x/day" -Force | Out-Null
Get-ScheduledTask -TaskName "JobSearch-Scan" | Select-Object TaskName, State
