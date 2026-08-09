$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseRoot = Join-Path $ProjectRoot 'release'
$Output = Join-Path $ReleaseRoot 'ARX-Desktop-win-x64'
$Work = Join-Path $ProjectRoot 'build\desktop'
$Entry = Join-Path $ProjectRoot 'packaging\arx_desktop_entry.py'

if ([Environment]::Is64BitProcess -ne $true) { throw 'Use a 64-bit Python interpreter to build ARX Desktop.' }
if (Test-Path -LiteralPath $Output) { Remove-Item -LiteralPath $Output -Recurse }
New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null

python -m PyInstaller --noconfirm --clean --windowed --onedir --name ARX `
    --paths (Join-Path $ProjectRoot 'src') --distpath $ReleaseRoot --workpath $Work $Entry
Move-Item -LiteralPath (Join-Path $ReleaseRoot 'ARX') -Destination $Output
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'packaging\README.txt') -Destination (Join-Path $Output 'README.txt')
