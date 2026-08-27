function ConvertTo-ArxReleaseVersion {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Version
    )

    $match = [regex]::Match(
        $Version,
        '^(?<major>0|[1-9]\d*)\.(?<minor>0|[1-9]\d*)\.(?<patch>0|[1-9]\d*)(?:(?<kind>rc|b)(?<number>[1-9]\d*))?$'
    )
    if (-not $match.Success) {
        throw 'Version must use the package form X.Y.Z, X.Y.ZrcN, or X.Y.ZbN.'
    }

    $baseVersion = "$($match.Groups['major'].Value).$($match.Groups['minor'].Value).$($match.Groups['patch'].Value)"
    $kind = $match.Groups['kind'].Value
    $number = if ($match.Groups['number'].Success) { $match.Groups['number'].Value } else { '0' }
    $stage = if ($kind -eq 'b') { "Beta $number" } elseif ($kind -eq 'rc') { "Release Candidate $number" } else { $null }

    [pscustomobject]@{
        PackageVersion   = $Version
        BaseVersion      = $baseVersion
        ArtifactVersion  = if ($kind) { "$baseVersion-$kind$number" } else { $baseVersion }
        FileVersion      = "$baseVersion.$number"
        ProductName      = "ARX $($match.Groups['major'].Value)"
        DisplayName      = "ARX $baseVersion$(if ($stage) { " $stage" })"
        PrereleaseKind   = $kind
        PrereleaseNumber = [int]$number
    }
}
