# Removes the scheduled pipeline task registered by install-schedule.ps1.
#
#   .\scripts\uninstall-schedule.ps1
param(
    [string[]]$TaskNames = @("velocity-bd-team pipeline", "velocity-bd-team feedback")
)

$ErrorActionPreference = "Stop"
foreach ($name in $TaskNames) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Host "No task named '$name' is registered."
        continue
    }
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
    Write-Host "Removed '$name'."
}
