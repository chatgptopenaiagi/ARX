param(
    [string]$Version = '4.0.0b2',
    [string]$ReleaseRoot,
    [long]$SourceDateEpoch = 0,
    [string]$IsccPath
)

$ErrorActionPreference = 'Stop'
$VersionMatch = [regex]::Match($Version, '^(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)(?:(?<kind>a|b|rc)(?<number>\d+))?$')
if (-not $VersionMatch.Success) {
    throw 'Version must use the package form X.Y.Z, X.Y.ZaN, X.Y.ZbN, or X.Y.ZrcN.'
}
$BaseVersion = "$($VersionMatch.Groups['major'].Value).$($VersionMatch.Groups['minor'].Value).$($VersionMatch.Groups['patch'].Value)"
$ReleaseComponent = if ($VersionMatch.Groups['number'].Success) { $VersionMatch.Groups['number'].Value } else { '0' }
$FileVersion = "$BaseVersion.$ReleaseComponent"
$ArtifactVersion = if ($VersionMatch.Groups['kind'].Success) {
    "$BaseVersion-$($VersionMatch.Groups['kind'].Value)$ReleaseComponent"
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

$PortableRoot = Join-Path $ReleaseRoot 'ARX-Desktop-win-x64'
$Executable = Join-Path $PortableRoot 'ARX.exe'
$InstallerScript = Join-Path $ProjectRoot 'packaging\arx-desktop.iss'
$Installer = Join-Path $ReleaseRoot "ARX-Desktop-Setup-win-x64-v$ArtifactVersion.exe"

$InstallerFullPath = [IO.Path]::GetFullPath($Installer)
if (-not ($InstallerFullPath + [IO.Path]::DirectorySeparatorChar).StartsWith($ReleaseRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create an installer outside the versioned release directory: $InstallerFullPath"
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

$PreviousSourceDateEpoch = [Environment]::GetEnvironmentVariable('SOURCE_DATE_EPOCH', 'Process')
$CompilerExitCode = $null
try {
    $env:SOURCE_DATE_EPOCH = [string]$SourceDateEpoch
    & $Compiler "/DMyAppVersion=$Version" "/DMyAppFileVersion=$FileVersion" "/DMyArtifactVersion=$ArtifactVersion" `
        "/DMyAppSourceDir=$PortableRoot" "/DMyOutputDir=$ReleaseRoot" $InstallerScript
    $CompilerExitCode = $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable('SOURCE_DATE_EPOCH', $PreviousSourceDateEpoch, 'Process')
}
if ($CompilerExitCode -ne 0) {
    throw "Inno Setup failed with exit code $CompilerExitCode."
}
if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    throw "Inno Setup did not produce the expected installer: $Installer"
}

& (Join-Path $PSScriptRoot 'write-release-checksums.ps1') -Version $Version -ReleaseRoot $ReleaseRoot
Write-Output "ARX Desktop installer created at $Installer"
