<#
.SYNOPSIS
    Run Microsoft's Zero Trust Assessment module with the registered Entra app.

.DESCRIPTION
    Called by UniMonitor when a Microsoft Zero Trust assessment is started with the
    PowerShell engine. It installs the ZeroTrustAssessment module when missing and
    connects app-only with the certificate UniMonitor keeps in its vault.

    Microsoft's module has no client-secret app-auth switch: app-only means a
    certificate (`-Certificate`), so this script imports the PFX UniMonitor writes to
    a private temporary folder, connects, runs Invoke-ZtAssessment and removes the
    certificate again. The PFX password travels in the environment, never on the
    command line.

    On failure the script exits non-zero with a readable message; UniMonitor then
    falls back to its Python engine and records the reason in the run.

.PARAMETER TenantId
    Directory (tenant) id of the client.

.PARAMETER ClientId
    Application (client) id of the UniMonitor app registration.

.PARAMETER OutputPath
    Folder for the generated report.

.PARAMETER PfxPath
    Optional. Path to a PFX holding the app certificate and its private key. Defaults
    to the ZT_CLIENT_PFX environment variable.

.PARAMETER PfxPassword
    Optional. PFX password. Defaults to ZT_CLIENT_PFX_PASSWORD.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$TenantId,
    [Parameter(Mandatory = $true)][string]$ClientId,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [string]$PfxPath = $env:ZT_CLIENT_PFX,
    [string]$PfxPassword = $env:ZT_CLIENT_PFX_PASSWORD
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($PfxPath) -or -not (Test-Path -LiteralPath $PfxPath)) {
    throw "App-only authentication needs the UniMonitor app certificate. Re-connect Microsoft 365 with a certificate, then run the assessment again."
}
if ([string]::IsNullOrWhiteSpace($PfxPassword)) {
    throw "The app certificate password was not supplied."
}

if (-not (Get-Module -ListAvailable -Name ZeroTrustAssessment)) {
    Install-Module ZeroTrustAssessment -Scope CurrentUser -Force -AllowClobber
}
Import-Module ZeroTrustAssessment -Force

$securePassword = ConvertTo-SecureString -String $PfxPassword -AsPlainText -Force
$imported = Import-PfxCertificate -FilePath $PfxPath -CertStoreLocation "Cert:\CurrentUser\My" -Password $securePassword
$thumbprint = $imported.Thumbprint

New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null

try {
    Write-Host -Object "Connecting to Microsoft Graph with app $ClientId in tenant $TenantId"
    Connect-ZtAssessment -TenantId $TenantId -ClientId $ClientId -Certificate $thumbprint
    Invoke-ZtAssessment -Path $OutputPath -ExportLog
}
finally {
    # The certificate must not outlive the run.
    if ($thumbprint) {
        Remove-Item -Path "Cert:\CurrentUser\My\$thumbprint" -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Get-ChildItem -Path $OutputPath -Filter *.html -Recurse -ErrorAction SilentlyContinue)) {
    throw "ZeroTrustAssessment produced no HTML report in $OutputPath"
}
