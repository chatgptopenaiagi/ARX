param(
    [string]$PythonExecutable = 'python',
    [string]$Version = '4.0.0b4',
    [string]$ReleaseRoot,
    [long]$SourceDateEpoch = 0,
    [switch]$AllowMissingInstaller
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
if (Test-Path -LiteralPath $ReleaseRoot) {
    Remove-Item -LiteralPath $ReleaseRoot -Recurse
}
New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null

$PythonPath = (Get-Command $PythonExecutable -ErrorAction Stop).Source
$PreviousSourceDateEpoch = [Environment]::GetEnvironmentVariable('SOURCE_DATE_EPOCH', 'Process')
$PreviousPythonHashSeed = [Environment]::GetEnvironmentVariable('PYTHONHASHSEED', 'Process')
$PreviousTimezone = [Environment]::GetEnvironmentVariable('TZ', 'Process')
try {
$env:SOURCE_DATE_EPOCH = [string]$SourceDateEpoch
$env:PYTHONHASHSEED = '0'
$env:TZ = 'UTC'
$SourceVersion = & $PythonPath -c "import sys; sys.path.insert(0, 'src'); import arx; print(arx.__version__)"
if ($LASTEXITCODE -ne 0 -or $SourceVersion -ne $Version) {
    throw "Source package version '$SourceVersion' does not match requested release version '$Version'."
}

& $PythonPath -m build --outdir $ReleaseRoot
if ($LASTEXITCODE -ne 0) { throw "Python distribution build failed with exit code $LASTEXITCODE." }
& $PythonPath (Join-Path $PSScriptRoot 'normalize-sdist.py') `
    --sdist (Join-Path $ReleaseRoot "arx_prescanner-$Version.tar.gz") `
    --version $Version --source-date-epoch $SourceDateEpoch
if ($LASTEXITCODE -ne 0) { throw "Deterministic sdist normalization failed with exit code $LASTEXITCODE." }

& (Join-Path $PSScriptRoot 'build-desktop.ps1') -PythonExecutable $PythonPath -Version $Version `
    -ReleaseRoot $ReleaseRoot -SourceDateEpoch $SourceDateEpoch
& (Join-Path $PSScriptRoot 'package-desktop-release.ps1') -Version $Version `
    -ReleaseRoot $ReleaseRoot -SourceDateEpoch $SourceDateEpoch

try {
    & (Join-Path $PSScriptRoot 'build-installer.ps1') -Version $Version `
        -ReleaseRoot $ReleaseRoot -SourceDateEpoch $SourceDateEpoch
} catch {
    if ($AllowMissingInstaller -and $_.Exception.Message -like '*ISCC.exe*was not found*') {
        Write-Warning 'Inno Setup is unavailable; the installer artifact was not built.'
    } else {
        throw
    }
}

& (Join-Path $PSScriptRoot 'write-release-checksums.ps1') -Version $Version -ReleaseRoot $ReleaseRoot
& $PythonPath (Join-Path $PSScriptRoot 'verify-release-assets.py') --release-root $ReleaseRoot --version $Version --artifact-version $ArtifactVersion
if ($LASTEXITCODE -ne 0) { throw "Release artifact verification failed with exit code $LASTEXITCODE." }

Write-Output "ARX $Version release assets built and verified under $ReleaseRoot"
} finally {
    [Environment]::SetEnvironmentVariable('SOURCE_DATE_EPOCH', $PreviousSourceDateEpoch, 'Process')
    [Environment]::SetEnvironmentVariable('PYTHONHASHSEED', $PreviousPythonHashSeed, 'Process')
    [Environment]::SetEnvironmentVariable('TZ', $PreviousTimezone, 'Process')
}
