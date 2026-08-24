param(
    [string]$Version = '4.0.0b1',
    [string]$ReleaseRoot
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
$ReleaseBase = Join-Path $ProjectRoot 'release'
if (-not $ReleaseRoot) {
    $ReleaseRoot = Join-Path $ReleaseBase "v$ArtifactVersion"
}
$ReleaseBaseFullPath = [IO.Path]::GetFullPath($ReleaseBase).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$ReleaseRoot = [IO.Path]::GetFullPath($ReleaseRoot).TrimEnd([IO.Path]::DirectorySeparatorChar)
if (-not ($ReleaseRoot + [IO.Path]::DirectorySeparatorChar).StartsWith($ReleaseBaseFullPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw "ReleaseRoot must be a version-specific directory under $ReleaseBase."
}

$Names = @(
    "arx_prescanner-$Version-py3-none-any.whl",
    "arx_prescanner-$Version.tar.gz",
    "ARX-Desktop-win-x64-v$ArtifactVersion.zip",
    "ARX-Desktop-Setup-win-x64-v$ArtifactVersion.exe"
)
$Artifacts = foreach ($Name in $Names) {
    $Path = Join-Path $ReleaseRoot $Name
    if (Test-Path -LiteralPath $Path -PathType Leaf) { Get-Item -LiteralPath $Path }
}
if (-not $Artifacts) {
    throw "No public release artifacts exist under $ReleaseRoot."
}
$ChecksumFile = Join-Path $ReleaseRoot 'SHA256SUMS.txt'
$ChecksumFullPath = [IO.Path]::GetFullPath($ChecksumFile)
if (-not ($ChecksumFullPath + [IO.Path]::DirectorySeparatorChar).StartsWith($ReleaseRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to write checksums outside the versioned release directory: $ChecksumFullPath"
}
$Lines = foreach ($Artifact in $Artifacts) {
    $Hash = (Get-FileHash -LiteralPath $Artifact.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $($Artifact.Name)"
}
[IO.File]::WriteAllLines($ChecksumFile, $Lines, [Text.UTF8Encoding]::new($false))
Write-Host "Release checksums created at $ChecksumFile"
