$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath 'bigbang.json' -PathType Leaf)) {
        throw 'Copy bigbang.example.json to bigbang.json and edit its database settings first.'
    }
    & .\bin\bigbang.exe
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}
