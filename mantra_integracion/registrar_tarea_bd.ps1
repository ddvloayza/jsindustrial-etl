param(
    [string]$TaskName = 'JS Industrial - Generar JSON Mantra',
    [string]$Server = 'SRV-02',
    [string]$OutDir = 'C:\Mantra\outbox'
)

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'run_exportar_json.ps1'
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Falta $launcher" }
if (-not (Test-Path -LiteralPath 'C:\Mantra\secrets\sql-mantra.bin' -PathType Leaf)) {
    throw 'Primero ejecute guardar_credencial_sql.ps1'
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "La tarea ya existe: $TaskName"
}

# Sin disparador: solo se ejecuta manualmente y exporta un contacto de prueba.
$arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Server "{1}" -OutDir "{2}" -Limit 1' -f $launcher, $Server, $OutDir
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Principal $principal -Settings $settings `
    -Description 'Prueba manual: genera un JSON de un contacto sin SQL Server Agent ni claves Mantra.' | Out-Null
Write-Output "Tarea de prueba creada: $TaskName. Ejecute Start-ScheduledTask para generar el JSON."
