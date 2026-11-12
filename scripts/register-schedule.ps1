# Registers a Windows scheduled task that syncs and classifies mail every 3 hours.
# Free: runs on this PC with the local Ollama model. Runs only while you are signed in,
# without opening a window. Output goes to logs\sync.log.
#
#   powershell -ExecutionPolicy Bypass -File scripts\register-schedule.ps1
#   Unregister-ScheduledTask -TaskName "Email Tracker sync"      # to remove it

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $repo ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "Missing $pythonw. Create the virtual environment first (README, step A)." }

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "-m ingest.run_scheduled" -WorkingDirectory $repo
# Every 3 hours, starting at 07:00 today. Missed runs (PC asleep or off) run as soon as possible.
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(7) -RepetitionInterval (New-TimeSpan -Hours 3)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 6)

Register-ScheduledTask -TaskName "Email Tracker sync" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Syncs 3 Gmail accounts (read-only) into Postgres and classifies new mail with local Ollama." -Force | Out-Null

Write-Host "Registered 'Email Tracker sync': every 3 hours while you are signed in. Log: $repo\logs\sync.log"
