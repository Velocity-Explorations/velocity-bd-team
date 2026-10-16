# Registers the weekly pipeline run in Windows Task Scheduler.
#
#   .\scripts\install-schedule.ps1                       # Mondays 06:00, current user
#   .\scripts\install-schedule.ps1 -Day Tuesday -At 07:30
#
# Overlap protection is twofold: the task's MultipleInstances policy is IgnoreNew, and
# run.py also takes data\pipeline.lock. Re-running this script replaces the existing task.
param(
    [string]$TaskName = "velocity-bd-team pipeline",
    [string]$Day = "Monday",
    [string]$At = "06:00"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "venv python not found at $python. Create the venv first (README.md)." }

$action = New-ScheduledTaskAction -Execute $python -Argument "run.py" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $At
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "velocity-bd-team: scrape portals, filter, review, digest. Logs in data\logs." -Force | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
Write-Host "Registered '$TaskName'"
Write-Host "  runs:     $python run.py  (in $repo)"
Write-Host "  trigger:  weekly, $Day at $At"
Write-Host "  overlap:  $($task.Settings.MultipleInstances) (plus data\pipeline.lock)"
Write-Host "  state:    $($task.State)"
Write-Host "Start it now with:  Start-ScheduledTask -TaskName '$TaskName'"
