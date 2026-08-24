[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string[]]$ArtifactPath,

    [Parameter(Mandatory)]
    [string]$PolicyPath,

    [Parameter(Mandatory)]
    [string]$OutputPath,

    [string]$SignToolPath,
    [switch]$AllowUnsignedPreSigning
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:OS -ne 'Windows_NT') {
    throw 'Authenticode verification must run on Windows.'
}

$Policy = Get-Content -LiteralPath $PolicyPath -Raw | ConvertFrom-Json
if ($Policy.schema_version -ne 1 -or $Policy.state -notin @('UNCONFIGURED', 'CONFIGURED')) {
    throw 'Signing policy is invalid or unsupported.'
}
if ($AllowUnsignedPreSigning -and $Policy.state -ne 'UNCONFIGURED') {
    throw 'Unsigned pre-signing verification requires an explicitly UNCONFIGURED policy.'
}

function Resolve-SignTool {
    param([string]$RequestedPath)

    if ($RequestedPath) {
        return (Resolve-Path -LiteralPath $RequestedPath -ErrorAction Stop).Path
    }
    $Command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($Command) {
        return $Command.Source
    }
    $Candidates = @(Get-ChildItem -LiteralPath "${env:ProgramFiles(x86)}\Windows Kits\10\bin" `
        -Filter signtool.exe -File -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName -Descending)
    if ($Candidates) {
        return $Candidates[0].FullName
    }
    throw 'Windows SDK signtool.exe is required for signed-artifact verification.'
}

$Records = @()
$AnyFailure = $false
$SignedCount = 0
$UnsignedCount = 0
foreach ($RequestedPath in $ArtifactPath) {
    $Resolved = (Resolve-Path -LiteralPath $RequestedPath -ErrorAction Stop).Path
    $Item = Get-Item -LiteralPath $Resolved
    if ($Item.PSIsContainer) {
        throw 'Authenticode target must be a file.'
    }
    $Hash = (Get-FileHash -LiteralPath $Resolved -Algorithm SHA256).Hash.ToLowerInvariant()
    $Signature = Get-AuthenticodeSignature -LiteralPath $Resolved
    $Status = [string]$Signature.Status
    $Errors = [Collections.Generic.List[string]]::new()

    if ($Status -eq 'NotSigned') {
        $UnsignedCount += 1
        if (-not $AllowUnsignedPreSigning) {
            $Errors.Add('Artifact is unsigned and unsigned pre-signing mode was not authorized.')
        }
        $Records += [ordered]@{
            artifact = $Item.Name
            size = $Item.Length
            sha256 = $Hash
            result = if ($Errors.Count) { 'FAIL' } else { 'UNSIGNED_EXPECTED_PRE_SIGNING' }
            authenticode_status = $Status
            publisher_subject = $null
            issuer = $null
            rfc3161_timestamp_present = $false
            signtool_policy_exit_code = $null
            digest_algorithm = $null
            errors = @($Errors)
        }
        if ($Errors.Count) {
            $AnyFailure = $true
        }
        continue
    }

    $SignedCount += 1
    if ($Policy.state -ne 'CONFIGURED') {
        $Errors.Add('A signed artifact cannot be accepted with an UNCONFIGURED production policy.')
    }
    if ($Status -ne 'Valid') {
        $Errors.Add("Get-AuthenticodeSignature returned $Status instead of Valid.")
    }
    $Publisher = if ($Signature.SignerCertificate) { $Signature.SignerCertificate.Subject } else { $null }
    $Issuer = if ($Signature.SignerCertificate) { $Signature.SignerCertificate.Issuer } else { $null }
    $ChainBuilt = $false
    $ChainSubjects = @()
    if ($Signature.SignerCertificate) {
        $Chain = [Security.Cryptography.X509Certificates.X509Chain]::new()
        try {
            $Chain.ChainPolicy.RevocationMode = `
                [Security.Cryptography.X509Certificates.X509RevocationMode]::Online
            $Chain.ChainPolicy.RevocationFlag = `
                [Security.Cryptography.X509Certificates.X509RevocationFlag]::EntireChain
            $ChainBuilt = $Chain.Build($Signature.SignerCertificate)
            $ChainSubjects = @(
                $Chain.ChainElements |
                    ForEach-Object { $_.Certificate.Subject }
            )
        } finally {
            $Chain.Dispose()
        }
    }
    if (-not $ChainBuilt) {
        $Errors.Add('The signer certificate did not build to a trusted Windows chain.')
    }
    if ($Policy.state -eq 'CONFIGURED') {
        if ($Publisher -cne $Policy.expected_publisher_subject) {
            $Errors.Add('Signer subject does not exactly match the approved publisher subject.')
        }
        $ApprovedIssuer = $false
        foreach ($ExpectedIssuer in @($Policy.expected_issuer_subjects)) {
            if ($Issuer -ceq $ExpectedIssuer -or $ChainSubjects -ccontains $ExpectedIssuer) {
                $ApprovedIssuer = $true
            }
        }
        if (-not $ApprovedIssuer) {
            $Errors.Add('Signer issuer is outside the approved issuer policy.')
        }
    }
    if (-not $Signature.TimeStamperCertificate) {
        $Errors.Add('Required RFC3161 timestamp certificate is missing.')
    }

    $SignTool = Resolve-SignTool -RequestedPath $SignToolPath
    $SignToolOutput = & $SignTool verify /pa /all /tw /v $Resolved 2>&1 | Out-String
    $SignToolExitCode = $LASTEXITCODE
    if ($SignToolExitCode -ne 0) {
        $Errors.Add('signtool policy/timestamp verification failed.')
    }
    $DigestVerified = $SignToolOutput -match '(?im)Hash of file \(sha256\):'
    if (-not $DigestVerified) {
        $Errors.Add('Expected SHA256 signature digest was not independently identified.')
    }

    $Records += [ordered]@{
        artifact = $Item.Name
        size = $Item.Length
        sha256 = $Hash
        result = if ($Errors.Count) { 'FAIL' } else { 'PASS_SIGNED' }
        authenticode_status = $Status
        publisher_subject = $Publisher
        issuer = $Issuer
        signer_chain_built = $ChainBuilt
        signer_chain_subjects = $ChainSubjects
        rfc3161_timestamp_present = [bool]$Signature.TimeStamperCertificate
        timestamp_subject = if ($Signature.TimeStamperCertificate) { $Signature.TimeStamperCertificate.Subject } else { $null }
        timestamp_issuer = if ($Signature.TimeStamperCertificate) { $Signature.TimeStamperCertificate.Issuer } else { $null }
        signtool_policy_exit_code = $SignToolExitCode
        digest_algorithm = if ($DigestVerified) { 'SHA256' } else { 'UNVERIFIED' }
        errors = @($Errors)
    }
    if ($Errors.Count) {
        $AnyFailure = $true
    }
}

if ($SignedCount -and $UnsignedCount) {
    $AnyFailure = $true
}
$Overall = if ($AnyFailure) {
    'FAIL'
} elseif ($SignedCount -eq $Records.Count) {
    'PASS_SIGNED'
} else {
    'UNSIGNED_EXPECTED_PRE_SIGNING'
}
$Evidence = [ordered]@{
    schema_version = 1
    record_type = 'authenticode_verification'
    observed_at = (Get-Date).ToUniversalTime().ToString('o')
    policy_state = $Policy.state
    overall = $Overall
    artifacts = $Records
    limitations = @(
        'UNSIGNED_EXPECTED_PRE_SIGNING is not a valid signature or publisher-trust result.',
        'RFC3161 signing-protocol provenance comes from the protected signing-operation record; this verifier confirms a trusted timestamp certificate and signtool /tw policy result.',
        'The SHA256 signtool-output check currently expects the English Windows SDK output label.',
        'SmartScreen and Smart App Control reputation remain separate from Authenticode verification.'
    )
}

$OutputFullPath = [IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $OutputFullPath) | Out-Null
[IO.File]::WriteAllText(
    $OutputFullPath,
    ($Evidence | ConvertTo-Json -Depth 10) + [Environment]::NewLine,
    [Text.UTF8Encoding]::new($false)
)
if ($AnyFailure) {
    throw "Authenticode verification failed. Evidence was preserved at $OutputFullPath"
}
Write-Output "Authenticode verification: $Overall"
