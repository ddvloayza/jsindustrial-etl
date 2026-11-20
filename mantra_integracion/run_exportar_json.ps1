param(
    [string]$Server = 'SRV-02',
    [string]$Database = 'JSIndustrial',
    [string]$EnvFile = '',
    [string]$OutDir = 'C:\Mantra\outbox',
    [string]$OutputPath = '',
    [int]$Limit = 0
)

$ErrorActionPreference = 'Stop'
if (-not $EnvFile) { $EnvFile = Join-Path $PSScriptRoot '.env' }
if ($Limit -lt 0) { throw 'Limit debe ser mayor o igual a cero' }
$logDir = 'C:\Mantra\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ("exportar_{0}.txt" -f (Get-Date -Format 'yyyyMMdd_HHmmss_fff'))
Start-Transcript -Path $logFile | Out-Null

# La tarea de Windows lee la cuenta SQL desde un .env local excluido de Git.
# El SP devuelve dos arreglos JSON; el script los envuelve sin cambiar sus valores.
if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "Falta el archivo de credenciales SQL: $EnvFile"
}
$sqlSettings = @{}
foreach ($line in [System.IO.File]::ReadAllLines($EnvFile, [System.Text.Encoding]::UTF8)) {
    if ($line.Trim().Length -eq 0 -or $line.TrimStart().StartsWith('#')) { continue }
    if ($line -notmatch '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
        throw "Formato invalido en ${EnvFile}: use NOMBRE=valor sin espacios alrededor de ="
    }
    $sqlSettings[$matches[1]] = $matches[2]
}
if (-not $sqlSettings['MANTRA_SQL_USER'] -or -not $sqlSettings['MANTRA_SQL_PASSWORD']) {
    throw "Complete MANTRA_SQL_USER y MANTRA_SQL_PASSWORD en $EnvFile"
}
$securePassword = ConvertTo-SecureString -String $sqlSettings['MANTRA_SQL_PASSWORD'] -AsPlainText -Force
$securePassword.MakeReadOnly()
$sqlCredential = [System.Data.SqlClient.SqlCredential]::new($sqlSettings['MANTRA_SQL_USER'], $securePassword)
$sqlSettings.Remove('MANTRA_SQL_PASSWORD')
$builder = [System.Data.SqlClient.SqlConnectionStringBuilder]::new()
$builder['Data Source'] = $Server
$builder['Initial Catalog'] = $Database
$builder['Integrated Security'] = $false
$builder['Application Name'] = 'JSIndustrial Mantra JSON Export'
$fechaProceso = (Get-Date).Date
$connection = [System.Data.SqlClient.SqlConnection]::new($builder.ToString(), $sqlCredential)
$command = $connection.CreateCommand()
$command.CommandType = [System.Data.CommandType]::StoredProcedure
$command.CommandText = 'dbo.JS_usp_ExportarCotizacionesMantra'
$command.CommandTimeout = 120
$command.Parameters.Add('@ComoJson', [System.Data.SqlDbType]::Bit).Value = 1
$command.Parameters.Add('@FechaProceso', [System.Data.SqlDbType]::Date).Value = $fechaProceso
if ($Limit -gt 0) {
    $command.Parameters.Add('@MaxContactos', [System.Data.SqlDbType]::Int).Value = $Limit
}

try {
    $connection.Open()
    $reader = $command.ExecuteReader()
    try {
        if (-not $reader.Read()) { throw 'El SP no devolvio ninguna fila' }
        $payload = $reader.GetString($reader.GetOrdinal('payload_json'))
        $ids = $reader.GetString($reader.GetOrdinal('ids_json'))
        if ($reader.Read()) { throw 'El SP devolvio mas de una fila' }
    }
    finally { $reader.Dispose() }
}
finally {
    $command.Dispose()
    $connection.Dispose()
}

$contacts = ConvertFrom-Json -InputObject $payload
$contactIds = ConvertFrom-Json -InputObject $ids
$contactCount = if ($payload.Trim() -eq '[]') { 0 } else { @($contacts).Count }
$idCount = if ($ids.Trim() -eq '[]') { 0 } else { @($contactIds).Count }
if ($contactCount -ne $idCount) { throw 'El SP devolvio contactos e IDs en cantidades distintas' }

$fechaJson = $fechaProceso.ToString('yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
$document = '{"format":"mantra-export-v1","fecha_proceso":"' + $fechaJson + '","contacts":' + $payload + ',"ids":' + $ids + '}'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$output = if ($OutputPath) { $OutputPath } else { Join-Path $OutDir "cotizaciones_$stamp.local.json" }
if (-not $output.EndsWith('.local.json', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'El archivo de salida debe terminar en .local.json'
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $output) | Out-Null
$temporary = "$output.tmp"
try {
    [System.IO.File]::WriteAllText($temporary, $document, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::Move($temporary, $output)
}
finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
}

Write-Output "JSON generado: $output; contactos: $contactCount"
Stop-Transcript | Out-Null
