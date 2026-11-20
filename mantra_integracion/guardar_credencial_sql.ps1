param(
    [string]$CredentialFile = 'C:\Mantra\secrets\sql-mantra.bin'
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security -ErrorAction Stop
$secretDir = Split-Path -Parent $CredentialFile
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null

# Solo SYSTEM y Administradores pueden leer la carpeta y el secreto.
& icacls.exe $secretDir /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'No se pudo dar acceso a SYSTEM y Administradores' }
& icacls.exe $secretDir /inheritance:r | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'No se pudo restringir la carpeta de secretos' }

$securePassword = Read-Host 'Contraseña del login SQL mantra' -AsSecureString
$bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $length = [System.Runtime.InteropServices.Marshal]::ReadInt32($bstr, -4)
    $plainBytes = New-Object byte[] $length
    [System.Runtime.InteropServices.Marshal]::Copy($bstr, $plainBytes, 0, $length)
    $encrypted = [System.Security.Cryptography.ProtectedData]::Protect(
        $plainBytes, $null, [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    )
    if ($null -eq $encrypted -or $encrypted.Length -eq 0) {
        throw 'No se pudo cifrar la credencial SQL'
    }
    [System.IO.File]::WriteAllBytes($CredentialFile, $encrypted)
}
finally {
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    if ($null -ne $plainBytes) { [Array]::Clear($plainBytes, 0, $plainBytes.Length) }
}

if (-not (Test-Path -LiteralPath $CredentialFile -PathType Leaf)) {
    throw 'No se creo el archivo de credencial SQL'
}
& icacls.exe $CredentialFile /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'No se pudo restringir el archivo de credencial' }
Write-Output "Credencial SQL cifrada para este servidor: $CredentialFile"
