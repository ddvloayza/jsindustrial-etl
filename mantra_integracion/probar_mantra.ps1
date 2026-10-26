param(
    [Parameter(Mandatory = $true)][string]$Phone,
    [string]$Name = ""
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$createdGroup = $false
$createdKey = $false

try {
    if (-not $env:MANTRA_GROUP_ID) {
        $env:MANTRA_GROUP_ID = Read-Host "Group ID de Mantra"
        $createdGroup = $true
    }
    if (-not $env:MANTRA_API_KEY) {
        $secureKey = Read-Host "API key de Mantra" -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        try {
            $env:MANTRA_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
        $createdKey = $true
    }
    $pythonArgs = @("$scriptDir\probar_mantra.py", "--phone", $Phone)
    if ($Name) { $pythonArgs += @("--name", $Name) }
    & python @pythonArgs
    exit $LASTEXITCODE
} finally {
    if ($createdKey) { Remove-Item Env:MANTRA_API_KEY -ErrorAction SilentlyContinue }
    if ($createdGroup) { Remove-Item Env:MANTRA_GROUP_ID -ErrorAction SilentlyContinue }
}
