param(
    [string]$PythonExe = "C:\Mantra\venv\Scripts\python.exe",
    [string]$OutDir = "C:\Mantra\outbox",
    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"
Remove-Item -Path 'Env:PYTHONHOME', 'Env:PYTHONPATH' -ErrorAction SilentlyContinue
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
$output = Join-Path $OutDir "cotizaciones_$stamp.local.json"
$arguments = @("$scriptDir\exportar_contactos.py", "--config", "$scriptDir\config.json", "--export-json", $output)
if ($Limit -lt 0) { throw "Limit debe ser mayor que cero" }
if ($Limit -gt 0) { $arguments += @("--limit", "$Limit") }
& $PythonExe @arguments
exit $LASTEXITCODE
