[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet(
        'PRE_INSTALL_STANDARD_USER',
        'POST_INSTALL_STANDARD_USER',
        'POST_UPGRADE_STANDARD_USER',
        'POST_UNINSTALL_STANDARD_USER',
        'PORTABLE_STANDARD_USER',
        'INSTALLER_ELEVATED_SHELL_OBSERVATION'
    )]
    [string]$Stage,

    [Parameter(Mandatory)]
    [string]$OutputPath,

    [string]$ArtifactPath,
    [string]$InstallDirectory = (Join-Path $env:ProgramFiles 'ARX'),
    [string]$ExpectedVersion
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ($env:OS -ne 'Windows_NT') {
    throw 'Windows lifecycle evidence collection must run on Windows.'
}

function Test-CurrentTokenElevated {
    $Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
    return $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-BroadWritableRule {
    param([Parameter(Mandatory)][string]$LiteralPath)

    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return @()
    }
    $BroadSids = @('S-1-1-0', 'S-1-5-11', 'S-1-5-32-545')
    $WriteMask = [Security.AccessControl.FileSystemRights]::Write -bor
        [Security.AccessControl.FileSystemRights]::Modify -bor
        [Security.AccessControl.FileSystemRights]::FullControl
    $Findings = @()
    foreach ($Rule in (Get-Acl -LiteralPath $LiteralPath).Access) {
        try {
            $Sid = $Rule.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value
        } catch {
            continue
        }
        if (
            $Sid -in $BroadSids -and
            $Rule.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
            (($Rule.FileSystemRights -band $WriteMask) -ne 0)
        ) {
            $Findings += [ordered]@{
                sid = $Sid
                rights = [string]$Rule.FileSystemRights
                inherited = [bool]$Rule.IsInherited
            }
        }
    }
    return $Findings
}

$OutputFullPath = [IO.Path]::GetFullPath($OutputPath)
$OutputDirectory = Split-Path -Parent $OutputFullPath
if (-not $OutputDirectory) {
    throw 'OutputPath must include a parent directory.'
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$IsElevated = Test-CurrentTokenElevated
$ExpectedElevated = $Stage -eq 'INSTALLER_ELEVATED_SHELL_OBSERVATION'
$TokenExpectationMet = $IsElevated -eq $ExpectedElevated
$InstallExists = Test-Path -LiteralPath $InstallDirectory -PathType Container
$ExecutablePath = Join-Path $InstallDirectory 'ARX.exe'
$ExecutableExists = Test-Path -LiteralPath $ExecutablePath -PathType Leaf
$BroadWritableRules = @(Get-BroadWritableRule -LiteralPath $InstallDirectory)

$Artifact = $null
if ($ArtifactPath) {
    $ResolvedArtifact = (Resolve-Path -LiteralPath $ArtifactPath -ErrorAction Stop).Path
    $Item = Get-Item -LiteralPath $ResolvedArtifact
    $Artifact = [ordered]@{
        name = $Item.Name
        size = $Item.Length
        sha256 = (Get-FileHash -LiteralPath $ResolvedArtifact -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$ExpectedInstallState = switch ($Stage) {
    'POST_INSTALL_STANDARD_USER' { 'PRESENT' }
    'POST_UPGRADE_STANDARD_USER' { 'PRESENT' }
    'POST_UNINSTALL_STANDARD_USER' { 'ABSENT' }
    default { 'NOT_ASSERTED' }
}
$InstallStateMet = switch ($ExpectedInstallState) {
    'PRESENT' { $InstallExists -and $ExecutableExists -and $BroadWritableRules.Count -eq 0 }
    'ABSENT' { -not $InstallExists }
    default { $true }
}

$LocalProviderRoot = Join-Path $env:LOCALAPPDATA 'ARX'
$Record = [ordered]@{
    schema_version = 1
    record_type = 'windows_lifecycle_observation'
    stage = $Stage
    observed_at = (Get-Date).ToUniversalTime().ToString('o')
    expected_version = $ExpectedVersion
    result = if ($TokenExpectationMet -and $InstallStateMet) { 'PASS' } else { 'FAIL' }
    host = [ordered]@{
        product_name = (Get-CimInstance Win32_OperatingSystem).Caption
        build = (Get-CimInstance Win32_OperatingSystem).BuildNumber
        architecture = $env:PROCESSOR_ARCHITECTURE
    }
    token = [ordered]@{
        elevated = $IsElevated
        expected_elevated = $ExpectedElevated
        expectation_met = $TokenExpectationMet
    }
    artifact = $Artifact
    installation = [ordered]@{
        expected_state = $ExpectedInstallState
        directory_present = $InstallExists
        executable_present = $ExecutableExists
        broad_writable_rule_count = $BroadWritableRules.Count
        broad_writable_rules = $BroadWritableRules
        expectation_met = $InstallStateMet
    }
    per_user_provider_data = [ordered]@{
        root_present = (Test-Path -LiteralPath $LocalProviderRoot)
        contents_inspected = $false
        credential_bytes_read = $false
    }
    limitations = @(
        'This collector does not install, upgrade, launch, or uninstall ARX.',
        'Interactive UAC, application launch, scan behavior, and uninstall user-data behavior require the accompanying checklist.'
    )
}

$Json = $Record | ConvertTo-Json -Depth 8
[IO.File]::WriteAllText($OutputFullPath, $Json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))

if ($Record.result -ne 'PASS') {
    throw "Lifecycle observation failed for stage $Stage. Evidence was preserved at $OutputFullPath"
}
Write-Output "Lifecycle observation: PASS ($Stage)"
