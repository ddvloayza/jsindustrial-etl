param(
    [string]$Fecha = "",
    [string]$PythonExe = "python",
    [int]$Limit = 0,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
# ZKBioTime puede definir rutas de Python 3.7; no deben entrar al venv del integrador.
Remove-Item -Path 'Env:PYTHONHOME', 'Env:PYTHONPATH' -ErrorAction SilentlyContinue
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$args = @("$scriptDir\exportar_contactos.py", "--config", "$scriptDir\config.json")
if ($Limit -lt 0) { throw "Limit debe ser mayor que cero" }
if ($Fecha) { $args += @("--fecha", $Fecha) }
if ($Limit -gt 0) { $args += @("--limit", "$Limit") }
if (-not $DryRun) { $args += "--apply" }
& $PythonExe @args
exit $LASTEXITCODE
