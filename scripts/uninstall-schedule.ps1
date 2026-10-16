# Removes the scheduled pipeline task registered by install-schedule.ps1.
#
#   .\scripts\uninstall-schedule.ps1
param(
    [string]$TaskName = "velocity-bd-team pipeline"
)

$ErrorActionPreference = "Stop"
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "No task named '$TaskName' is registered."
    exit 0
}
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed '$TaskName'."
