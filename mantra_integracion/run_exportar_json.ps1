param(
    [string]$Server = 'SRV-02',
    [string]$Database = 'JSIndustrial',
    [string]$OutDir = 'C:\Mantra\outbox',
    [int]$Limit = 0
)

$ErrorActionPreference = 'Stop'
if ($Limit -lt 0) { throw 'Limit debe ser mayor o igual a cero' }

# SQL Server Agent ejecuta este script con su identidad de Windows.
# El SP devuelve dos arreglos JSON; el script los envuelve sin cambiar sus valores.
$fechaProceso = (Get-Date).Date
$connection = [System.Data.SqlClient.SqlConnection]::new(
    "Data Source=$Server;Initial Catalog=$Database;Integrated Security=SSPI;Application Name=JSIndustrial Mantra JSON Export"
)
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
$output = Join-Path $OutDir "cotizaciones_$stamp.local.json"
$temporary = "$output.tmp"
try {
    [System.IO.File]::WriteAllText($temporary, $document, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::Move($temporary, $output)
}
finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
}

Write-Output "JSON generado: $output; contactos: $contactCount"
