param(
    [Parameter(Mandatory = $true)][string]$Hora,
    [Parameter(Mandatory = $true)][string]$SharePath,
    [string]$PythonExe = "C:\Mantra\venv\Scripts\python.exe",
    [string]$Nombre = "Mantra - Enviar archivos"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $scriptDir "run_enviar_archivos.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$launcher`" -SharePath `"$SharePath`" -PythonExe `"$PythonExe`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Hora
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $Nombre -Action $action -Trigger $trigger -Settings $settings -Description "Lee JSON desde la carpeta compartida, envía contactos a Mantra y registra éxitos localmente"
