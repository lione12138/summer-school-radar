# Register (or refresh) the Windows scheduled task that runs the daily scan.
#
# Runs scan_and_publish.ps1 every day at 10:00. The settings make it robust to
# the machine being asleep, off, or away from home at 10:00:
#   - StartWhenAvailable: if the machine was off/asleep at 10:00, run as soon as
#     it is next available instead of skipping the day.
#   - WakeToRun: wake the machine from sleep to run (works on AC power).
#   - RunOnlyIfNetworkAvailable: don't bother starting with no network; the
#     script also rechecks connectivity and skips cleanly if it is unusable.
#
# Re-run this any time to update the task definition.

$ErrorActionPreference = "Stop"

$taskName = "SummerSchoolRadar-DailyScan"
$repo = Split-Path -Parent $PSScriptRoot
$script = Join-Path $repo "scripts\scan_and_publish.ps1"

if (-not (Test-Path $script)) {
    throw "Cannot find scan script at $script"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory $repo

$trigger = New-ScheduledTaskTrigger -Daily -At 10:00AM

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -RunOnlyIfNetworkAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

# Run as the current user, in their interactive session, so the cached git
# credential (and any browser for Playwright) is available. No password stored.
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Daily scan + publish for Summer School Radar (runs locally to avoid Cloudflare datacenter-IP blocks)." `
    -Force | Out-Null

Write-Host "Registered scheduled task '$taskName' (daily at 10:00)."
Get-ScheduledTask -TaskName $taskName | Format-List TaskName, State
