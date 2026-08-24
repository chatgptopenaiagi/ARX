[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ProjectRoot,
    [long]$RequestedEpoch = 0
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$MinimumZipEpoch = 315532800L  # 1980-01-01T00:00:00Z
$MaximumPeEpoch = 4294967295L # unsigned 32-bit PE timestamp ceiling

if ($RequestedEpoch -gt 0) {
    $Epoch = $RequestedEpoch
} else {
    $Git = (Get-Command git -ErrorAction Stop).Source
    $Value = & $Git -C $ProjectRoot log -1 --format=%ct HEAD
    if ($LASTEXITCODE -ne 0 -or $Value -notmatch '^\d+$') {
        throw 'Unable to derive SOURCE_DATE_EPOCH from the checked-out Git commit.'
    }
    $Epoch = [long]$Value
}

if ($Epoch -lt $MinimumZipEpoch -or $Epoch -gt $MaximumPeEpoch) {
    throw 'SOURCE_DATE_EPOCH must fit ZIP and PE timestamp representations.'
}

Write-Output $Epoch
