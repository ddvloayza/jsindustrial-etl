param(
    [string]$Hora = '05:00',
    [string]$TaskName = 'JS Industrial - Exportar y enviar Mantra',
    [string]$PythonExe = 'C:\Mantra\venv\Scripts\python.exe'
)

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'run_mantra_local.ps1'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Falta $launcher" }
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Falta Python: $PythonExe" }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'config.local.json') -PathType Leaf)) {
    throw 'Falta config.local.json'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.env') -PathType Leaf)) {
    throw 'Falta .env con SQL y Mantra'
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "La tarea ya existe: $TaskName"
}

$horaLocal = [DateTime]::ParseExact($Hora, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
$arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -PythonExe "{1}"' -f $launcher, $PythonExe
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Daily -At $horaLocal
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
    -Settings $settings -Description 'Genera JSON y envia contactos a Mantra; registra exitos en SQL.' | Out-Null
$oldTask = Get-ScheduledTask -TaskName 'JS Industrial - Generar JSON Mantra' -ErrorAction SilentlyContinue
if ($oldTask) { Disable-ScheduledTask -InputObject $oldTask | Out-Null }
Write-Output "Tarea diaria creada: $TaskName; hora local del servidor: $Hora"
