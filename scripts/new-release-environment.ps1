[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$TargetPath,

    [string]$BasePython = 'python',
    [string]$RequirementsPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd([IO.Path]::DirectorySeparatorChar)
$Target = [IO.Path]::GetFullPath($TargetPath).TrimEnd([IO.Path]::DirectorySeparatorChar)
if (($Target + [IO.Path]::DirectorySeparatorChar).StartsWith(
    $ProjectRoot + [IO.Path]::DirectorySeparatorChar,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw 'The release virtual environment must be outside the source checkout.'
}
if (Test-Path -LiteralPath $Target) {
    throw "Refusing to overwrite an existing release environment: $Target"
}
if (-not $RequirementsPath) {
    $RequirementsPath = Join-Path $ProjectRoot 'packaging\release-build-requirements.txt'
}
$Requirements = (Resolve-Path -LiteralPath $RequirementsPath -ErrorAction Stop).Path
$Python = (Get-Command $BasePython -ErrorAction Stop).Source
$Identity = & $Python -c "import platform, struct; print(platform.python_version()); print(struct.calcsize('P') * 8)"
if ($LASTEXITCODE -ne 0 -or $Identity.Count -ne 2) {
    throw 'Unable to identify the base Python interpreter.'
}
if ($Identity[0] -ne '3.12.13' -or $Identity[1] -ne '64') {
    throw "Release builds require CPython 3.12.13 x64; observed $($Identity -join ' / ')."
}

& $Python -m venv $Target
if ($LASTEXITCODE -ne 0) {
    throw "Virtual environment creation failed with exit code $LASTEXITCODE."
}
$EnvironmentPython = Join-Path $Target 'Scripts\python.exe'
& $EnvironmentPython -m pip install --disable-pip-version-check --requirement $Requirements
if ($LASTEXITCODE -ne 0) {
    throw "Locked release tool installation failed with exit code $LASTEXITCODE."
}
& $EnvironmentPython -m pip check
if ($LASTEXITCODE -ne 0) {
    throw "Locked release environment failed pip check with exit code $LASTEXITCODE."
}
Write-Output $EnvironmentPython
