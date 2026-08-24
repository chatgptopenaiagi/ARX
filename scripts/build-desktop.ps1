param(
    [string]$PythonExecutable = 'python',
    [string]$Version = '4.0.0b2',
    [string]$ReleaseRoot,
    [long]$SourceDateEpoch = 0
)

$ErrorActionPreference = 'Stop'
$VersionMatch = [regex]::Match($Version, '^(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)(?:(?<kind>a|b|rc)(?<number>\d+))?$')
if (-not $VersionMatch.Success) {
    throw 'Version must use the package form X.Y.Z, X.Y.ZaN, X.Y.ZbN, or X.Y.ZrcN.'
}
$BaseVersion = "$($VersionMatch.Groups['major'].Value).$($VersionMatch.Groups['minor'].Value).$($VersionMatch.Groups['patch'].Value)"
$ArtifactVersion = if ($VersionMatch.Groups['kind'].Success) {
    "$BaseVersion-$($VersionMatch.Groups['kind'].Value)$($VersionMatch.Groups['number'].Value)"
} else {
    $BaseVersion
}

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourceDateEpoch = & (Join-Path $PSScriptRoot 'resolve-source-date-epoch.ps1') `
    -ProjectRoot $ProjectRoot -RequestedEpoch $SourceDateEpoch
$ReleaseBase = Join-Path $ProjectRoot 'release'
if (-not $ReleaseRoot) {
    $ReleaseRoot = Join-Path $ReleaseBase "v$ArtifactVersion"
}
$ReleaseBaseFullPath = [IO.Path]::GetFullPath($ReleaseBase).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$ReleaseRoot = [IO.Path]::GetFullPath($ReleaseRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
if (-not ($ReleaseRoot + [IO.Path]::DirectorySeparatorChar).StartsWith($ReleaseBaseFullPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw "ReleaseRoot must be a version-specific directory under $ReleaseBase."
}

$Output = Join-Path $ReleaseRoot 'ARX-Desktop-win-x64'
$Intermediate = Join-Path $ReleaseRoot 'ARX'
$Work = Join-Path $ProjectRoot "build\desktop\$ArtifactVersion"
$Entry = Join-Path $ProjectRoot 'packaging\arx_desktop_entry.py'
$VersionInfo = Join-Path $ProjectRoot 'packaging\windows-version-info.txt'

$PythonCommand = Get-Command $PythonExecutable -ErrorAction Stop
$PythonPath = $PythonCommand.Source
$PythonArchitecture = & $PythonPath -c "import struct; print(struct.calcsize('P') * 8)"
if ($LASTEXITCODE -ne 0 -or $PythonArchitecture -ne '64') {
    throw 'Use a 64-bit Python interpreter to build ARX Desktop.'
}

foreach ($target in @($Output, $Intermediate)) {
    $TargetFullPath = [IO.Path]::GetFullPath($target)
    if (-not ($TargetFullPath + [IO.Path]::DirectorySeparatorChar).StartsWith($ReleaseRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to replace desktop output outside the versioned release directory: $TargetFullPath"
    }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse
    }
}
New-Item -ItemType Directory -Path $ReleaseRoot,$Work -Force | Out-Null

$PreviousSourceDateEpoch = [Environment]::GetEnvironmentVariable('SOURCE_DATE_EPOCH', 'Process')
$PreviousPythonHashSeed = [Environment]::GetEnvironmentVariable('PYTHONHASHSEED', 'Process')
$PreviousTimezone = [Environment]::GetEnvironmentVariable('TZ', 'Process')
$PyInstallerExitCode = $null
try {
    $env:SOURCE_DATE_EPOCH = [string]$SourceDateEpoch
    $env:PYTHONHASHSEED = '0'
    $env:TZ = 'UTC'
    & $PythonPath -m PyInstaller --noconfirm --clean --noupx --windowed --onedir --name ARX `
        --contents-directory _internal --version-file $VersionInfo `
        --paths (Join-Path $ProjectRoot 'src') --distpath $ReleaseRoot --workpath $Work `
        --specpath $Work $Entry
    $PyInstallerExitCode = $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable('SOURCE_DATE_EPOCH', $PreviousSourceDateEpoch, 'Process')
    [Environment]::SetEnvironmentVariable('PYTHONHASHSEED', $PreviousPythonHashSeed, 'Process')
    [Environment]::SetEnvironmentVariable('TZ', $PreviousTimezone, 'Process')
}
if ($PyInstallerExitCode -ne 0) { throw "PyInstaller failed with exit code $PyInstallerExitCode." }

Move-Item -LiteralPath $Intermediate -Destination $Output
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'packaging\README.txt') -Destination (Join-Path $Output 'README.txt')
Copy-Item -LiteralPath (Join-Path $ProjectRoot 'LICENSE') -Destination (Join-Path $Output 'LICENSE.txt')

if (-not (Test-Path -LiteralPath (Join-Path $Output 'ARX.exe') -PathType Leaf)) {
    throw 'PyInstaller did not produce ARX.exe.'
}
if (-not (Test-Path -LiteralPath (Join-Path $Output '_internal') -PathType Container)) {
    throw 'PyInstaller did not produce the required _internal runtime directory.'
}

Write-Output "ARX Desktop release created at $Output"
