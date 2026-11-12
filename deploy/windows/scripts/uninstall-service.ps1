# UniMonitor Windows Service uninstaller helper
# Run as Administrator

param(
    [string]$InstallDir = "C:\Program Files\UniMonitor",
    [string]$ServiceName = "UniMonitor"
)

$nssm = Join-Path $InstallDir "nssm.exe"

Write-Host "Stopping and removing UniMonitor service..." -ForegroundColor Yellow

if (Test-Path $nssm) {
    & $nssm stop $ServiceName 2>$null
    & $nssm remove $ServiceName confirm
} else {
    sc.exe stop $ServiceName 2>$null
    sc.exe delete $ServiceName
}

Write-Host "Service removed." -ForegroundColor Green
