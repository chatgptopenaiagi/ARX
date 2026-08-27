param(
    [string]$Version = '3.0.0rc1',
    [string]$IsccPath
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'versioning.ps1')
$ReleaseVersion = ConvertTo-ArxReleaseVersion -Version $Version
$FileVersion = $ReleaseVersion.FileVersion
$ArtifactVersion = $ReleaseVersion.ArtifactVersion
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseRoot = Join-Path $ProjectRoot 'release'
$PortableRoot = Join-Path $ReleaseRoot 'ARX-Desktop-win-x64'
$Executable = Join-Path $PortableRoot 'ARX.exe'
$InstallerScript = Join-Path $ProjectRoot 'packaging\arx-desktop.iss'
$Installer = Join-Path $ReleaseRoot "ARX-Desktop-Setup-win-x64-v$ArtifactVersion.exe"
$ChecksumFile = Join-Path $ReleaseRoot "SHA256SUMS-v$ArtifactVersion.txt"

$ReleaseFullPath = [IO.Path]::GetFullPath($ReleaseRoot).TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
$InstallerFullPath = [IO.Path]::GetFullPath($Installer)
if (-not $InstallerFullPath.StartsWith($ReleaseFullPath, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create an installer outside the release directory: $InstallerFullPath"
}
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    throw "Missing portable desktop build: $Executable. Run scripts\build-desktop.ps1 first."
}
if (-not (Test-Path -LiteralPath (Join-Path $PortableRoot '_internal') -PathType Container)) {
    throw 'The portable desktop build is incomplete: _internal is missing.'
}

if ($IsccPath) {
    $Compiler = (Resolve-Path -LiteralPath $IsccPath -ErrorAction Stop).Path
} else {
    $Command = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
    $Candidates = @(
        if ($Command) { $Command.Source }
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe')
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe')
        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe')
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe')
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) }
    $Compiler = $Candidates | Select-Object -First 1
}
if (-not $Compiler) {
    throw 'Inno Setup 6 or 7 compiler (ISCC.exe) was not found. Install Inno Setup or pass -IsccPath.'
}

& $Compiler "/DMyAppVersion=$Version" "/DMyAppFileVersion=$FileVersion" "/DMyArtifactVersion=$ArtifactVersion" "/DMyAppProductName=$($ReleaseVersion.ProductName)" "/DMyAppDisplayName=$($ReleaseVersion.DisplayName)" $InstallerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw "Inno Setup did not produce the expected installer: $Installer"
}

$InstallerHash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
$ChecksumLine = "$InstallerHash  $(Split-Path -Leaf $Installer)"
$ExistingLines = if (Test-Path -LiteralPath $ChecksumFile -PathType Leaf) {
    Get-Content -LiteralPath $ChecksumFile | Where-Object { $_ -notmatch '  ARX-Desktop-Setup-win-x64-' }
} else {
    @()
}
[IO.File]::WriteAllLines($ChecksumFile, @($ExistingLines) + $ChecksumLine, [Text.UTF8Encoding]::new($false))

Write-Host "ARX Desktop installer created at $Installer"
Write-Host "Installer checksum recorded in $ChecksumFile"
