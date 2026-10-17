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
    [string]$At = "06:00",
    [string]$FeedbackTaskName = "velocity-bd-team feedback",
    [string]$FeedbackAt = "18:00",
    [string]$RemindAt = "08:00",
    [string]$SummaryDay = "Monday",
    [string]$SummaryAt = "09:00"
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "venv python not found at $python. Create the venv first (README.md)." }

# A short job that must never overlap itself and should catch up when the machine wakes.
function Register-Job([string]$Name, [string]$Arguments, $Trigger, [int]$LimitMinutes, [string]$Description) {
    $action = New-ScheduledTaskAction -Execute $python -Argument $Arguments -WorkingDirectory $repo
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes $LimitMinutes) `
        -StartWhenAvailable -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Trigger -Settings $settings `
        -Description $Description -Force | Out-Null
    Write-Host "Registered '$Name'"
    Write-Host "  runs:     $python $Arguments"
}

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

# Daily Slack sync: thread replies into notes, dashboard decisions onto the cards.
$fbAction = New-ScheduledTaskAction -Execute $python -Argument "run.py --feedback-only" -WorkingDirectory $repo
$fbTrigger = New-ScheduledTaskTrigger -Daily -At $FeedbackAt
$fbSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 20) `
    -StartWhenAvailable -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $FeedbackTaskName -Action $fbAction -Trigger $fbTrigger -Settings $fbSettings `
    -Description "velocity-bd-team: Slack thread notes into the ledger, decisions onto the cards." -Force | Out-Null
Write-Host "Registered '$FeedbackTaskName'"
Write-Host "  runs:     $python run.py --feedback-only"
Write-Host "  trigger:  daily at $FeedbackAt"

# The portal assistant's scheduled posts (docs/ASSISTANT.md).
Register-Job "velocity-bd-team reminders" "-m assistant remind" (New-ScheduledTaskTrigger -Daily -At $RemindAt) 10 `
    "velocity-bd-team: post Slack reminders for calls marked Pursue that are due within 14 days."
Write-Host "  trigger:  daily at $RemindAt"
Register-Job "velocity-bd-team weekly summary" "-m assistant post-summary" `
    (New-ScheduledTaskTrigger -Weekly -DaysOfWeek $SummaryDay -At $SummaryAt) 10 `
    "velocity-bd-team: post each portal's weekly summary and scraper health to Slack."
Write-Host "  trigger:  weekly, $SummaryDay at $SummaryAt"
