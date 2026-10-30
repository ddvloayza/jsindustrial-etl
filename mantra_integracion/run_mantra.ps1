param(
    [string]$Fecha = "",
    [string]$PythonExe = "python",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$args = @("$scriptDir\exportar_contactos.py", "--config", "$scriptDir\config.json")
if ($Fecha) { $args += @("--fecha", $Fecha) }
if (-not $DryRun) { $args += "--apply" }
& $PythonExe @args
exit $LASTEXITCODE
