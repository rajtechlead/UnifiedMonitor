<#
.SYNOPSIS
    Run Microsoft's Zero Trust Assessment and import the result into UniMonitor.

.DESCRIPTION
    Installs the ZeroTrustAssessment module if it is missing, connects to a tenant,
    runs Invoke-ZtAssessment, then posts the machine-readable report
    (ZeroTrustAssessmentReport.json) to UniMonitor's /api/v1/zerotrust/import.
    The import is read-only: nothing is changed in the tenant, and the report stays
    on this machine unless -UniMonitorUrl is supplied.

    Use -ImportOnly to upload a report from an earlier run.

.PARAMETER Tenant
    Tenant domain or id, e.g. contoso.onmicrosoft.com. Prompts for sign-in.

.PARAMETER Path
    Output folder for the assessment. Defaults to .\ZeroTrustReport.

.PARAMETER UniMonitorUrl
    Base URL of UniMonitor, e.g. https://unimonitor.contoso.com. Omit to only
    write the report locally.

.PARAMETER ApiToken
    UniMonitor API token (an administrator's bearer token). Prompted securely when
    -UniMonitorUrl is set and this is not.

.PARAMETER UniMonitorTenantId
    UniMonitor tenant id the run belongs to. Defaults to the only tenant the
    account can see; required when there are several.

.PARAMETER ImportOnly
    Skip the assessment and upload the report already at -Path.

.EXAMPLE
    .\Invoke-UniMonitorZeroTrust.ps1 -Tenant contoso.onmicrosoft.com `
        -UniMonitorUrl https://unimonitor.contoso.com -UniMonitorTenantId 2c1f...

.NOTES
    Requires PowerShell 7. The assessment itself needs Global Reader (Global
    Administrator for the first consent) and can take hours on a large tenant.
#>
[CmdletBinding()]
param(
    [string]$Tenant,
    [string]$Path = ".\ZeroTrustReport",
    [string]$UniMonitorUrl,
    [string]$ApiToken,
    [string]$UniMonitorTenantId,
    [switch]$ImportOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Find-ReportJson {
    param([string]$Root)
    if (-not (Test-Path $Root)) { return $null }

    $candidates = @(
        (Join-Path $Root "ZeroTrustAssessmentReport.json"),
        (Join-Path $Root "zt-export\ZeroTrustAssessmentReport.json"),
        (Join-Path (Join-Path $Root "ZeroTrustReport") "ZeroTrustAssessmentReport.json")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { return (Resolve-Path $candidate).Path }
    }
    $found = Get-ChildItem -Path $Root -Filter "ZeroTrustAssessmentReport.json" -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

if (-not $ImportOnly) {
    if (-not $Tenant) {
        throw "Pass -Tenant (for example contoso.onmicrosoft.com) or use -ImportOnly with an existing report."
    }

    if (-not (Get-Command Invoke-ZtAssessment -ErrorAction SilentlyContinue)) {
        Write-Host "Installing the ZeroTrustAssessment module for the current user..."
        Install-Module ZeroTrustAssessment -Scope CurrentUser -Force
    }

    if (-not (Get-Command Connect-ZtAssessment -ErrorAction SilentlyContinue)) {
        throw "Connect-ZtAssessment is still unavailable. Open a new PowerShell 7 session and run this script again."
    }

    Write-Host "Connecting to $Tenant (sign in when prompted)..."
    Connect-ZtAssessment -Tenant $Tenant

    New-Item -ItemType Directory -Path $Path -Force | Out-Null
    Write-Host "Running the assessment into $Path. This can take a long time; do not close the window."
    Invoke-ZtAssessment -Path $Path -NoBrowser
}

$report = Find-ReportJson -Root $Path
if (-not $report) {
    throw "No ZeroTrustAssessmentReport.json found under $Path. Run without -ImportOnly, or point -Path at the run's folder."
}

Write-Host "Report: $report"

if (-not $UniMonitorUrl) {
    Write-Host "No -UniMonitorUrl supplied. Upload $report on the Zero Trust Assessment page, or re-run with -UniMonitorUrl."
    return
}

if (-not $ApiToken) {
    $secure = Read-Host "UniMonitor API token" -AsSecureString
    $ApiToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    )
}

$payload = Get-Content -Path $report -Raw | ConvertFrom-Json
$body = @{
    source    = "microsoft"
    tenant_id = $UniMonitorTenantId
    payload   = $payload
} | ConvertTo-Json -Depth 40 -Compress

$endpoint = "$($UniMonitorUrl.TrimEnd('/'))/api/v1/zerotrust/import"
Write-Host "Uploading to $endpoint ..."
$response = Invoke-RestMethod -Method Post -Uri $endpoint -Body $body -ContentType "application/json" `
    -Headers @{ Authorization = "Bearer $ApiToken" }

Write-Host ("Imported {0} checks for {1}: score {2}%." -f `
    $response.run.total, $response.run.platform, $response.run.score)
