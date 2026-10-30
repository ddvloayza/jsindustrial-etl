param(
    [string]$Fecha = "",
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$args = @("$scriptDir\exportar_contactos.py", "--config", "$scriptDir\config.json", "--apply")
if ($Fecha) { $args += @("--fecha", $Fecha) }
& $PythonExe @args
exit $LASTEXITCODE
