param(
    [string]$PythonExe = 'C:\Mantra\venv\Scripts\python.exe',
    [string]$OutDir = 'C:\Mantra\outbox',
    [int]$Limit = 0,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
if ($Limit -lt 0) { throw 'Limit debe ser mayor o igual a cero' }
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw "Falta Python: $PythonExe" }
$config = Join-Path $PSScriptRoot 'config.local.json'
if (-not (Test-Path -LiteralPath $config -PathType Leaf)) { throw "Falta $config" }
$exporter = Join-Path $PSScriptRoot 'run_exportar_json.ps1'
$sender = Join-Path $PSScriptRoot 'exportar_contactos.py'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$jsonFile = Join-Path $OutDir "cotizaciones_$stamp.local.json"

& $exporter -OutDir $OutDir -OutputPath $jsonFile -Limit $Limit
if (-not (Test-Path -LiteralPath $jsonFile -PathType Leaf)) { throw "No se genero $jsonFile" }

# ZKBioTime puede definir rutas de Python 3.7 ajenas al entorno virtual.
Remove-Item -Path 'Env:PYTHONHOME', 'Env:PYTHONPATH' -ErrorAction SilentlyContinue
$arguments = @($sender, '--config', $config, '--json-file', $jsonFile)
if (-not $DryRun) { $arguments += '--apply' }
& $PythonExe @arguments
if ($LASTEXITCODE -ne 0) { throw "Fallo el procesamiento de $jsonFile" }
Write-Output "Lote procesado: $jsonFile"
