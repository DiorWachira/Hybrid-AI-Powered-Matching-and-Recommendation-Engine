param(
    [ValidateRange(1, 60)][int]$IntervalMinutes = 1
)

$ErrorActionPreference = 'Stop'
$taskName = 'JobBridge-GraphSync'
$backend = $PSScriptRoot
$python = Join-Path (Split-Path $backend -Parent) 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project Python environment not found.' }
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    throw 'JobBridge-GraphSync already exists. Review it before replacing or removing it.'
}
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$statusFile = Join-Path $env:LOCALAPPDATA 'JobBridge\graph-sync-status.json'
$arguments = '-m app.db.graph_sync --limit 1000 --status-file "' + $statusFile + '"'
$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $backend
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Project PostgreSQL outbox to Neo4j; uses root .env, no credentials in task arguments.' | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output "Installed $taskName every $IntervalMinutes minute(s) while this Windows user is signed in."