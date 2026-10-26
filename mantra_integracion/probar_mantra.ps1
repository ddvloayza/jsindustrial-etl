param(
    [Parameter(Mandatory = $true)][string]$Phone,
    [string]$Name = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonArgs = @("$scriptDir\probar_mantra.py", "--phone", $Phone)
if ($Name) { $pythonArgs += @("--name", $Name) }
& python @pythonArgs
exit $LASTEXITCODE
