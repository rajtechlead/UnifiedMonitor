<#
.SYNOPSIS
    Run Microsoft's Zero Trust Assessment module with an app registration.

.DESCRIPTION
    Called by UniMonitor when a Microsoft Zero Trust assessment is started from the
    Zero Trust page. It installs the ZeroTrustAssessment module when missing, connects
    with the registered Entra app through the module's app-auth switch, runs
    Invoke-ZtAssessment and leaves the module's own HTML/JSON report in -OutputPath.

    UniMonitor copies the HTML report into its "ZT assessments" folder. If the module
    or the app-auth switch is unavailable the script exits non-zero; UniMonitor then
    falls back to its Python engine, so the run still produces a report.

.PARAMETER TenantId
    Directory (tenant) id of the client.

.PARAMETER ClientId
    Application (client) id of the UniMonitor app registration.

.PARAMETER ClientSecret
    Optional. When omitted the secret is read from the ZT_CLIENT_SECRET environment
    variable, which is how UniMonitor invokes this script so the secret never appears
    in a process command line. Certificate auth is intentionally not accepted here:
    UniMonitor keeps private keys in its vault.

.PARAMETER OutputPath
    Folder for the generated report.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TenantId,
    [Parameter(Mandatory = $true)][string]$ClientId,
    [string]$ClientSecret = $env:ZT_CLIENT_SECRET,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Get-Module -ListAvailable -Name ZeroTrustAssessment)) {
    Install-Module ZeroTrustAssessment -Scope CurrentUser -Force -AllowClobber
}
Import-Module ZeroTrustAssessment -Force

if ([string]::IsNullOrWhiteSpace($ClientSecret)) {
    throw "A client secret is required via -ClientSecret or ZT_CLIENT_SECRET"
}

New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

Connect-ZtAssessment -TenantId $TenantId -ApplicationId $ClientId -ClientSecret $ClientSecret -UseAppAuth
Invoke-ZtAssessment -Path $OutputPath

if (-not (Get-ChildItem -Path $OutputPath -Filter *.html -Recurse -ErrorAction SilentlyContinue)) {
    throw "ZeroTrustAssessment produced no HTML report in $OutputPath"
}
