param(
    [string]$Version = '4.0.0b6'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'versioning.ps1')
$ReleaseVersion = ConvertTo-ArxReleaseVersion -Version $Version
$ArtifactVersion = $ReleaseVersion.ArtifactVersion
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseRoot = Join-Path $ProjectRoot 'release'
$DesktopDirectory = Join-Path $ReleaseRoot 'ARX-Desktop-win-x64'
$Executable = Join-Path $DesktopDirectory 'ARX.exe'
$Archive = Join-Path $ReleaseRoot "ARX-Desktop-win-x64-v$ArtifactVersion.zip"
$ChecksumFile = Join-Path $ReleaseRoot "SHA256SUMS-v$ArtifactVersion.txt"

$ReleaseFullPath = [IO.Path]::GetFullPath($ReleaseRoot).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
foreach ($target in @($DesktopDirectory,$Archive,$ChecksumFile)) {
    $targetFullPath = [IO.Path]::GetFullPath($target)
    if (-not $targetFullPath.StartsWith($ReleaseFullPath,[StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to package a target outside the release directory: $targetFullPath"
    }
}

if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { throw "Missing desktop executable: $Executable" }
if (-not (Test-Path -LiteralPath (Join-Path $DesktopDirectory '_internal') -PathType Container)) { throw 'Missing _internal runtime directory.' }

$forbiddenDirectories = @('.git','.venv','tests','__pycache__','.pytest_cache')
$forbiddenFiles = Get-ChildItem -LiteralPath $DesktopDirectory -Recurse -Force | Where-Object {
    ($_.PSIsContainer -and $_.Name -in $forbiddenDirectories) -or
    (-not $_.PSIsContainer -and ($_.Extension -in @('.py','.pyc','.spec','.key','.pem') -or $_.Name -in @('.env','credentials.json')))
}
if ($forbiddenFiles) {
    throw "Forbidden development or private files found in release payload: $($forbiddenFiles.FullName -join ', ')"
}

if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive }
if (Test-Path -LiteralPath $ChecksumFile) { Remove-Item -LiteralPath $ChecksumFile }
Compress-Archive -LiteralPath $DesktopDirectory -DestinationPath $Archive -CompressionLevel Optimal

$ExecutableHash = (Get-FileHash -LiteralPath $Executable -Algorithm SHA256).Hash.ToLowerInvariant()
$ArchiveHash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
$lines = @(
    "$ExecutableHash  ARX-Desktop-win-x64\ARX.exe",
    "$ArchiveHash  $(Split-Path -Leaf $Archive)"
)
[IO.File]::WriteAllLines($ChecksumFile,$lines,[Text.UTF8Encoding]::new($false))

Write-Host "Desktop archive created at $Archive"
Write-Host "Checksums created at $ChecksumFile"
