param(
    [Parameter(Mandatory = $true)][string]$SharePath,
    [string]$PythonExe = "C:\Mantra\venv\Scripts\python.exe",
    [string]$LocalDir = "C:\Mantra\inbox"
)

$ErrorActionPreference = "Stop"
Remove-Item -Path 'Env:PYTHONHOME', 'Env:PYTHONPATH' -ErrorAction SilentlyContinue
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path $LocalDir | Out-Null
foreach ($source in Get-ChildItem -Path $SharePath -Filter "*.local.json" -File | Sort-Object Name) {
    $localFile = Join-Path $LocalDir $source.Name
    $doneFile = "$localFile.done"
    if (Test-Path $doneFile) { continue }
    Copy-Item -LiteralPath $source.FullName -Destination $localFile -Force
    & $PythonExe "$scriptDir\exportar_contactos.py" --config "$scriptDir\config.sender.json" --json-file $localFile --offline --apply
    if ($LASTEXITCODE -eq 0) {
        New-Item -ItemType File -Force -Path $doneFile | Out-Null
    } else {
        Write-Error "Falló el envío de $localFile; se reintentará en la siguiente ejecución"
    }
}
