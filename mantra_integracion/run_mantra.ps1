param(
    [string]$Fecha = "",
    [switch]$ContactsOnly
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$args = @("$scriptDir\exportar_contactos.py", "--config", "$scriptDir\config.json", "--send")
if ($Fecha) { $args += @("--fecha", $Fecha) }
if ($ContactsOnly) { $args += "--contacts-only" }
& python @args
exit $LASTEXITCODE
