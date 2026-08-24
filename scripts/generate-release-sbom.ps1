[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$WheelPath,

    [Parameter(Mandatory)]
    [string]$OutputPath,

    [string]$PythonExecutable = 'python'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Wheel = (Resolve-Path -LiteralPath $WheelPath -ErrorAction Stop).Path
$Python = (Get-Command $PythonExecutable -ErrorAction Stop).Source
$CycloneDx = Join-Path (Split-Path -Parent $Python) 'cyclonedx-py.exe'
if (-not (Test-Path -LiteralPath $CycloneDx -PathType Leaf)) {
    throw 'cyclonedx-py.exe is missing from the selected locked release environment.'
}
$Output = [IO.Path]::GetFullPath($OutputPath)
$OutputParent = Split-Path -Parent $Output
if (-not $OutputParent) {
    throw 'SBOM output must have a parent directory.'
}
New-Item -ItemType Directory -Path $OutputParent -Force | Out-Null

$TempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
    [IO.Path]::DirectorySeparatorChar
) + [IO.Path]::DirectorySeparatorChar
$Scratch = Join-Path $TempBase ('arx-sbom-' + [guid]::NewGuid().ToString('N'))
$ScratchFull = [IO.Path]::GetFullPath($Scratch).TrimEnd([IO.Path]::DirectorySeparatorChar)
if (-not ($ScratchFull + [IO.Path]::DirectorySeparatorChar).StartsWith(
    $TempBase,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw 'Refusing to create SBOM scratch storage outside the system temporary directory.'
}

try {
    & $Python -m venv --without-pip $ScratchFull
    if ($LASTEXITCODE -ne 0) {
        throw "SBOM virtual environment creation failed with exit code $LASTEXITCODE."
    }
    $ScratchPython = Join-Path $ScratchFull 'Scripts\python.exe'
    $SiteDirectory = & $ScratchPython -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"
    if ($LASTEXITCODE -ne 0 -or -not $SiteDirectory) {
        throw 'Unable to resolve the isolated SBOM site-packages directory.'
    }
    & $Python -m pip install --disable-pip-version-check --no-deps --target $SiteDirectory $Wheel
    if ($LASTEXITCODE -ne 0) {
        throw "Isolated wheel installation for SBOM failed with exit code $LASTEXITCODE."
    }
    & $CycloneDx environment $ScratchPython `
        --pyproject (Join-Path $ProjectRoot 'pyproject.toml') `
        --mc-type application --spec-version 1.6 --output-reproducible `
        --output-format JSON --output-file $Output --validate
    if ($LASTEXITCODE -ne 0) {
        throw "CycloneDX generation or validation failed with exit code $LASTEXITCODE."
    }
    & $Python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8')); assert d.get('bomFormat')=='CycloneDX'" $Output
    if ($LASTEXITCODE -ne 0) {
        throw 'Generated SBOM failed independent JSON identity validation.'
    }
} finally {
    if (Test-Path -LiteralPath $ScratchFull) {
        $ResolvedScratch = (Resolve-Path -LiteralPath $ScratchFull -ErrorAction Stop).Path
        if (-not ($ResolvedScratch + [IO.Path]::DirectorySeparatorChar).StartsWith(
            $TempBase,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            throw 'Refusing to remove SBOM scratch storage outside the system temporary directory.'
        }
        Remove-Item -LiteralPath $ResolvedScratch -Recurse -Force
    }
}
Write-Output "CycloneDX SBOM: VALID ($([IO.Path]::GetFileName($Output)))"
