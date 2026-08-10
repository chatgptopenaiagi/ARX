param(
    [string]$PythonExecutable = 'python'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseRoot = Join-Path $ProjectRoot 'release'
$Output = Join-Path $ReleaseRoot 'ARX-Desktop-win-x64'
$Work = Join-Path $ProjectRoot 'build\desktop'
$Entry = Join-Path $ProjectRoot 'packaging\arx_desktop_entry.py'
$VersionInfo = Join-Path $ProjectRoot 'packaging\windows-version-info.txt'

$PythonCommand = Get-Command $PythonExecutable -ErrorAction Stop
$PythonPath = $PythonCommand.Source
$PythonArchitecture = & $PythonPath -c "import struct; print(struct.calcsize('P') * 8)"
if ($LASTEXITCODE -ne 0 -or $PythonArchitecture -ne '64') {
    throw 'Use a 64-bit Python interpreter to build ARX Desktop.'
}

$ReleaseFullPath = [IO.Path]::GetFullPath($ReleaseRoot).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$OutputFullPath = [IO.Path]::GetFullPath($Output)
if (-not $OutputFullPath.StartsWith($ReleaseFullPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to replace output outside the release directory: $OutputFullPath"
}
if (Test-Path -LiteralPath $Output) { Remove-Item -LiteralPath $Output -Recurse }
New-Item -ItemType Directory -Path $ReleaseRoot,$Work -Force | Out-Null

& $PythonPath -m PyInstaller --noconfirm --clean --windowed --onedir --name ARX `
    --contents-directory _internal --version-file $VersionInfo `
    --paths (Join-Path $ProjectRoot 'src') --distpath $ReleaseRoot --workpath $Work `
    --specpath $Work $Entry
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE." }

Move-Item -LiteralPath (Join-Path $ReleaseRoot 'ARX') -Destination $Output
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'packaging\README.txt') -Destination (Join-Path $Output 'README.txt')

if (-not (Test-Path -LiteralPath (Join-Path $Output 'ARX.exe') -PathType Leaf)) {
    throw 'PyInstaller did not produce ARX.exe.'
}
if (-not (Test-Path -LiteralPath (Join-Path $Output '_internal') -PathType Container)) {
    throw 'PyInstaller did not produce the required _internal runtime directory.'
}

Write-Host "ARX Desktop release created at $Output"
