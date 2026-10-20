# Registers the pipeline and the portal assistant's jobs in Windows Task Scheduler.
#
#   .\scripts\install-schedule.ps1                       # Sundays 22:00, current user
#   .\scripts\install-schedule.ps1 -Day Tuesday -At 07:30
#   .\scripts\install-schedule.ps1 -RequestsAt "09:07"   # approved requests once a day
#
# Overlap protection is twofold: each task's MultipleInstances policy is IgnoreNew, and
# run.py also takes data\pipeline.lock. The scheduled pipeline and feedback runs wait up to
# 30 minutes for the lock (-WaitLockMinutes) in case approved requests are being carried
# out. Re-running this script replaces the existing tasks.
#
# Every task starts python through conhost.exe --headless, so no console window opens on
# the desktop, for python or for anything it starts. The catch: Task Scheduler's Last Run
# Result then reads 0 even when a run fails, so look for failures in data\logs and the
# Slack alerts instead.
param(
    [string]$TaskName = "velocity-bd-team pipeline",
    [string]$Day = "Sunday",
    [string]$At = "22:00",
    [string]$FeedbackTaskName = "velocity-bd-team feedback",
    [string]$FeedbackAt = "18:00",
    [string]$RemindAt = "08:00",
    [string]$SummaryDay = "Monday",
    [string]$SummaryAt = "09:00",
    [string[]]$RequestsAt = @("12:07", "17:07"),
    [int]$WaitLockMinutes = 30
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "venv python not found at $python. Create the venv first (README.md)." }
$conhost = Join-Path $env:SystemRoot "System32\conhost.exe"

# conhost's arguments for running python, with run.py's arguments, in a console nobody sees.
function Headless([string]$Arguments) { "--headless `"$python`" $Arguments" }

# A short job that must never overlap itself and should catch up when the machine wakes.
function Register-Job([string]$Name, [string]$Arguments, $Trigger, [int]$LimitMinutes, [string]$Description) {
    $action = New-ScheduledTaskAction -Execute $conhost -Argument (Headless $Arguments) -WorkingDirectory $repo
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes $LimitMinutes) `
        -StartWhenAvailable -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Trigger -Settings $settings `
        -Description $Description -Force | Out-Null
    Write-Host "Registered '$Name'"
    Write-Host "  runs:     $python $Arguments"
}

$action = New-ScheduledTaskAction -Execute $conhost -Argument (Headless "run.py --wait-lock $WaitLockMinutes") -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Day -At $At
# Sunday night, so the results are in before the Monday meeting. WakeToRun wakes the PC if
# someone put it to sleep; on mains power it is set never to sleep.
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "velocity-bd-team: scrape portals, filter, review, digest. Logs in data\logs." -Force | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
Write-Host "Registered '$TaskName'"
Write-Host "  runs:     $python run.py --wait-lock $WaitLockMinutes  (in $repo)"
Write-Host "  trigger:  weekly, $Day at $At"
Write-Host "  overlap:  $($task.Settings.MultipleInstances) (plus data\pipeline.lock)"
Write-Host "  state:    $($task.State)"
Write-Host "Start it now with:  Start-ScheduledTask -TaskName '$TaskName'"

# Daily Slack sync: thread replies into notes, dashboard decisions onto the cards.
$fbAction = New-ScheduledTaskAction -Execute $conhost -Argument (Headless "run.py --feedback-only --wait-lock $WaitLockMinutes") -WorkingDirectory $repo
$fbTrigger = New-ScheduledTaskTrigger -Daily -At $FeedbackAt
$fbSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 60) `
    -StartWhenAvailable -RunOnlyIfNetworkAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $FeedbackTaskName -Action $fbAction -Trigger $fbTrigger -Settings $fbSettings `
    -Description "velocity-bd-team: Slack thread notes into the ledger, decisions onto the cards." -Force | Out-Null
Write-Host "Registered '$FeedbackTaskName'"
Write-Host "  runs:     $python run.py --feedback-only --wait-lock $WaitLockMinutes"
Write-Host "  trigger:  daily at $FeedbackAt"

# The portal assistant's jobs (docs/ASSISTANT.md). They run from run.py, the one place that
# wires components together.
Register-Job "velocity-bd-team reminders" "run.py --remind" (New-ScheduledTaskTrigger -Daily -At $RemindAt) 10 `
    "velocity-bd-team: post Slack reminders for calls marked Pursue that are due within 14 days."
Write-Host "  trigger:  daily at $RemindAt"
Register-Job "velocity-bd-team weekly summary" "run.py --post-summary" `
    (New-ScheduledTaskTrigger -Weekly -DaysOfWeek $SummaryDay -At $SummaryAt) 10 `
    "velocity-bd-team: post each portal's weekly summary and scraper health to Slack."
Write-Host "  trigger:  weekly, $SummaryDay at $SummaryAt"

# Approved change requests, twice a day by default. Most passes find nothing and exit in
# seconds without taking the lock; an approved scan runs the pipeline for one portal, hence
# the two-hour limit. The odd start minute keeps passes off the hour, when the other jobs start.
$requestsTriggers = $RequestsAt | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }
Register-Job "velocity-bd-team requests" "run.py --apply-requests" $requestsTriggers 120 `
    "velocity-bd-team: carry out change requests approved on the dashboard's Requests page."
Write-Host "  trigger:  daily at $($RequestsAt -join ' and ')"
