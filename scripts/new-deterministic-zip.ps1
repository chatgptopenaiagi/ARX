[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$SourceDirectory,
    [Parameter(Mandatory)]
    [string]$DestinationPath,
    [Parameter(Mandatory)]
    [string]$RootName,
    [Parameter(Mandatory)]
    [long]$SourceDateEpoch
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Source = (Resolve-Path -LiteralPath $SourceDirectory -ErrorAction Stop).Path.TrimEnd(
    [IO.Path]::DirectorySeparatorChar,
    [IO.Path]::AltDirectorySeparatorChar
)
if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
    throw 'SourceDirectory must be an existing directory.'
}
if ($RootName -notmatch '^[A-Za-z0-9._-]+$') {
    throw 'RootName contains unsupported archive characters.'
}

$Destination = [IO.Path]::GetFullPath($DestinationPath)
$DestinationDirectory = Split-Path -Parent $Destination
if (-not $DestinationDirectory) {
    throw 'DestinationPath must include a parent directory.'
}
$SourcePrefix = $Source + [IO.Path]::DirectorySeparatorChar
if (($Destination + [IO.Path]::DirectorySeparatorChar).StartsWith($SourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'DestinationPath must be outside SourceDirectory.'
}

$Timestamp = [DateTimeOffset]::FromUnixTimeSeconds($SourceDateEpoch)
if ($Timestamp.UtcDateTime -lt [datetime]'1980-01-01T00:00:00Z') {
    throw 'SourceDateEpoch predates the ZIP timestamp range.'
}

New-Item -ItemType Directory -Force -Path $DestinationDirectory | Out-Null
if (Test-Path -LiteralPath $Destination) {
    Remove-Item -LiteralPath $Destination
}

$Items = [Collections.Generic.List[object]]::new()
foreach ($File in (Get-ChildItem -LiteralPath $Source -File -Recurse -Force)) {
    $Relative = [IO.Path]::GetRelativePath($Source, $File.FullName).Replace('\', '/')
    $Items.Add([pscustomobject]@{
        SourcePath = $File.FullName
        EntryName = "$RootName/$Relative"
    })
}
$Items.Sort([Comparison[object]]{
    param($Left, $Right)
    [StringComparer]::Ordinal.Compare($Left.EntryName, $Right.EntryName)
})

$Stream = [IO.File]::Open($Destination, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try {
    $Archive = [IO.Compression.ZipArchive]::new($Stream, [IO.Compression.ZipArchiveMode]::Create, $false)
    try {
        foreach ($Item in $Items) {
            $Entry = $Archive.CreateEntry($Item.EntryName, [IO.Compression.CompressionLevel]::Optimal)
            $Entry.LastWriteTime = $Timestamp
            $Entry.ExternalAttributes = 0
            $InputStream = [IO.File]::Open($Item.SourcePath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
            $Output = $Entry.Open()
            try {
                $InputStream.CopyTo($Output)
            } finally {
                $Output.Dispose()
                $InputStream.Dispose()
            }
        }
    } finally {
        $Archive.Dispose()
    }
} finally {
    $Stream.Dispose()
}

Write-Output "Deterministic ZIP created: $Destination"
