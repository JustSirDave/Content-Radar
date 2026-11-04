# Registers the Content Radar scheduled task: every 4 hours, and run as soon as possible
# after a missed start (the computer was off or asleep). The program itself also catches up
# per source from its last success. Run this once yourself; it changes Windows settings.
param(
    [string]$ProjectDir = (Resolve-Path "$PSScriptRoot\.."),
    [string]$TaskName = "ContentRadar"
)

$python = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "No virtual environment at $python. Create it first: python -m venv .venv"
}

$action = New-ScheduledTaskAction -Execute $python -Argument "-m radar run" -WorkingDirectory $ProjectDir
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 4)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Content Radar: collect, rank and write the digest" | Out-Null
Write-Host "Registered '$TaskName': every 4 hours, runs after a missed start. Remove with: Unregister-ScheduledTask -TaskName $TaskName"
