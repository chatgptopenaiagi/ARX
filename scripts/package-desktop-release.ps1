param(
    [string]$Version = '4.0.0b4',
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

$DesktopDirectory = Join-Path $ReleaseRoot 'ARX-Desktop-win-x64'
$Executable = Join-Path $DesktopDirectory 'ARX.exe'
$Archive = Join-Path $ReleaseRoot "ARX-Desktop-win-x64-v$ArtifactVersion.zip"

foreach ($target in @($DesktopDirectory,$Archive)) {
    $targetFullPath = [IO.Path]::GetFullPath($target)
    if (-not ($targetFullPath + [IO.Path]::DirectorySeparatorChar).StartsWith($ReleaseRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to package a target outside the versioned release directory: $targetFullPath"
    }
}

if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { throw "Missing desktop executable: $Executable" }
if (-not (Test-Path -LiteralPath (Join-Path $DesktopDirectory '_internal') -PathType Container)) { throw 'Missing _internal runtime directory.' }
if (-not (Test-Path -LiteralPath (Join-Path $DesktopDirectory 'README.txt') -PathType Leaf)) { throw 'Missing portable README.txt.' }
if (-not (Test-Path -LiteralPath (Join-Path $DesktopDirectory 'LICENSE.txt') -PathType Leaf)) { throw 'Missing portable LICENSE.txt.' }

$forbiddenDirectories = @('.git','.venv','tests','__pycache__','.pytest_cache')
$forbiddenFiles = Get-ChildItem -LiteralPath $DesktopDirectory -Recurse -Force | Where-Object {
    ($_.PSIsContainer -and $_.Name -in $forbiddenDirectories) -or
    (-not $_.PSIsContainer -and ($_.Extension -in @('.py','.pyc','.spec','.key','.pem','.dpapi') -or $_.Name -in @('.env','credentials.json','secrets.json','external-transmissions.jsonl')))
}
if ($forbiddenFiles) {
    throw "Forbidden development or private files found in release payload: $($forbiddenFiles.FullName -join ', ')"
}

& (Join-Path $PSScriptRoot 'new-deterministic-zip.ps1') `
    -SourceDirectory $DesktopDirectory -DestinationPath $Archive `
    -RootName 'ARX-Desktop-win-x64' -SourceDateEpoch $SourceDateEpoch

& (Join-Path $PSScriptRoot 'write-release-checksums.ps1') -Version $Version -ReleaseRoot $ReleaseRoot
Write-Output "Desktop archive created at $Archive"
