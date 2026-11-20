param(
    [string]$TaskName = 'JS Industrial - Generar JSON Mantra',
    [string]$Server = 'SRV-02',
    [string]$OutDir = 'C:\Mantra\outbox',
    [string]$Hora = '07:00'
)

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'run_exportar_json.ps1'
if (-not (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
    throw "Primero registre la tarea de prueba: $TaskName"
}
$horaLocal = [DateTime]::ParseExact($Hora, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
$arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Server "{1}" -OutDir "{2}"' -f $launcher, $Server, $OutDir
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$trigger = New-ScheduledTaskTrigger -Daily -At $horaLocal
Set-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger | Out-Null
Write-Output "Exportacion diaria activada a las $Hora (hora local del servidor): $TaskName"
