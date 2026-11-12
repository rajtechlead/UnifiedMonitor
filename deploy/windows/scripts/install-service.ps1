# UniMonitor Windows Service installer helper
# Run as Administrator from the UniMonitor install directory

param(
    [string]$InstallDir = "C:\Program Files\UniMonitor",
    [int]$Port = 8000,
    [string]$ServiceName = "UniMonitor"
)

$ErrorActionPreference = "Stop"

Write-Host "Installing UniMonitor Windows Service..." -ForegroundColor Cyan

$exe    = Join-Path $InstallDir "UniMonitor.exe"
$nssm   = Join-Path $InstallDir "nssm.exe"

if (!(Test-Path $exe)) {
    Write-Error "UniMonitor.exe not found at $InstallDir — is UniMonitor installed?"
    exit 1
}

if (Test-Path $nssm) {
    Write-Host "Using NSSM to install service..."
    & $nssm install $ServiceName $exe "start --host 0.0.0.0 --port $Port"
    & $nssm set $ServiceName AppDirectory $InstallDir
    & $nssm set $ServiceName AppEnvironmentExtra "UNIMONITOR_ENV=production"
    & $nssm set $ServiceName Description "UniMonitor — Unified M365 Security Monitoring & GRC Platform"
    & $nssm set $ServiceName Start SERVICE_AUTO_START
    & $nssm start $ServiceName
} else {
    Write-Host "NSSM not found — using sc.exe..."
    sc.exe create $ServiceName binPath= "`"$exe`" start --host 0.0.0.0 --port $Port" `
        start= auto DisplayName= "UniMonitor"
    sc.exe description $ServiceName "UniMonitor — Unified M365 Security Monitoring & GRC Platform"
    sc.exe start $ServiceName
}

Write-Host ""
Write-Host "Service installed and started." -ForegroundColor Green
Write-Host "Open http://localhost:$Port in your browser."
