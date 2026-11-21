<#
.SYNOPSIS
    Builds UniMonitor-Setup-<version>-x64.exe with a single command.

.DESCRIPTION
    Runs the whole packaging pipeline that INSTALL.md documents:

      1. checks Python / Node / git
      2. creates (or reuses) .build-venv and installs PyInstaller + the app
      3. builds the React frontend and stages it in unimonitor/static
      4. regenerates branding/icon.ico if it is missing
      5. freezes the app with PyInstaller
      6. fetches the NSSM service helper into the bundle
      7. installs NSIS automatically when it is missing (winget, then choco)
      8. builds the installer with makensis
      9. smoke-tests the packaged exe and writes a portable zip

    Every step fails loudly: the exit code is non-zero if any tool or output
    is missing, so CI and a local run behave the same way.

    Run it from anywhere:
        powershell -ExecutionPolicy Bypass -File scripts\build-windows-installer.ps1
    or double-click build-windows-installer.cmd.

.PARAMETER Version
    Installer version (default: the version in pyproject.toml).

.PARAMETER SkipFrontend
    Reuse the already-built frontend in unimonitor/static.

.PARAMETER SkipSmokeTest
    Skip running the packaged UniMonitor.exe --help.

.PARAMETER NssmSha256
    Optional expected SHA-256 for the NSSM zip. A published NSSM release is not
    code-signed, so pass a hash you trust to pin the download; without it the
    script prints the hash it downloaded so you can verify it once.

.EXAMPLE
    .\scripts\build-windows-installer.ps1 -Version 1.2.0
#>
[CmdletBinding()]
param(
    [string]$Version,
    [switch]$SkipFrontend,
    [switch]$SkipSmokeTest,
    [string]$NssmSha256,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Split-Path -Parent $PSScriptRoot
$NssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$BuildDir = Join-Path $Root ".build"
$VenvPython = Join-Path $Root ".build-venv\Scripts\python.exe"

function Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Fail([string]$Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Invoke-Checked([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        Fail "$Exe $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

Push-Location $Root
try {
    # -- 0. Version ------------------------------------------------------------
    if (-not $Version) {
        $project = Get-Content (Join-Path $Root "pyproject.toml") -Raw
        if ($project -match '(?m)^version\s*=\s*"([^"]+)"') {
            $Version = $Matches[1]
        } else {
            Fail "No -Version given and pyproject.toml has no version line"
        }
    }
    $Version = $Version.TrimStart('v')
    Write-Host "UniMonitor installer build $Version" -ForegroundColor Green

    # -- 1. Prerequisites ------------------------------------------------------
    Step "Checking build tools"
    $pythonCmd = Get-Command $Python -ErrorAction SilentlyContinue
    if (-not $pythonCmd) { Fail "Python not found. Install Python 3.12+ from https://python.org/downloads and re-run." }
    $pythonVersion = (& $Python -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
    if ([version]$pythonVersion -lt [version]"3.12") {
        Fail "Python $pythonVersion found; 3.12 or newer is required."
    }

    if (-not $SkipFrontend) {
        if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
            Fail "npm not found. Install Node.js 20 LTS from https://nodejs.org and re-run."
        }
    }

    # -- 2. Build virtual environment ------------------------------------------
    if (-not (Test-Path $VenvPython)) {
        Step "Creating .build-venv"
        Invoke-Checked $Python @("-m", "venv", (Join-Path $Root ".build-venv"))
    }
    Step "Installing Python dependencies"
    Invoke-Checked $VenvPython @("-m", "pip", "install", "--upgrade", "pip", "--quiet")
    Invoke-Checked $VenvPython @(
        "install", "--quiet",
        "pyinstaller>=6.16.0,<7",
        "-e", ".[production]"
    )

    # -- 3. Frontend -----------------------------------------------------------
    if ($SkipFrontend) {
        if (-not (Test-Path (Join-Path $Root "unimonitor/static"))) {
            Fail "-SkipFrontend was given but unimonitor/static does not exist"
        }
        Write-Host "Reusing existing unimonitor/static"
    } else {
        Step "Building the React frontend"
        Push-Location (Join-Path $Root "frontend")
        try {
            Invoke-Checked "npm" @("ci")
            Invoke-Checked "npm" @("run", "build")
        } finally {
            Pop-Location
        }
        $static = Join-Path $Root "unimonitor/static"
        New-Item -ItemType Directory -Force -Path $static | Out-Null
        Copy-Item -Path (Join-Path $Root "frontend/dist/*") -Destination $static -Recurse -Force
    }

    # -- 4. Branding -----------------------------------------------------------
    $icon = Join-Path $Root "branding/icon.ico"
    if (-not (Test-Path $icon)) {
        Step "branding/icon.ico is missing -- regenerating it"
        Invoke-Checked $VenvPython @("scripts/make_icon.py")
        if (-not (Test-Path $icon)) { Fail "scripts/make_icon.py did not create branding/icon.ico" }
    }

    # -- 5. Freeze the application ---------------------------------------------
    Step "Running PyInstaller"
    Invoke-Checked $VenvPython @(
        "-m", "pyinstaller",
        "deploy/windows/unimonitor.spec",
        "--clean", "--noconfirm"
    )
    $exe = Join-Path $Root "dist/UniMonitor/UniMonitor.exe"
    if (-not (Test-Path $exe)) { Fail "PyInstaller finished but dist/UniMonitor/UniMonitor.exe is missing" }

    # -- 6. NSSM (Windows service helper) --------------------------------------
    Step "Fetching NSSM"
    New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
    $zip = Join-Path $BuildDir "nssm.zip"
    Invoke-WebRequest -Uri $NssmUrl -OutFile $zip -UseBasicParsing
    $hash = (Get-FileHash -Path $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($NssmSha256) {
        if ($hash -ne $NssmSha256.ToLowerInvariant()) {
            Fail "NSSM checksum mismatch: expected $NssmSha256, downloaded $hash"
        }
    } else {
        Write-Host "NSSM SHA256 $hash (pass -NssmSha256 $hash to pin it next time)"
    }
    $nssmTmp = Join-Path $BuildDir "nssm"
    if (Test-Path $nssmTmp) { Remove-Item -Recurse -Force $nssmTmp }
    Expand-Archive -Path $zip -DestinationPath $nssmTmp -Force
    $nssmExe = Get-ChildItem -Path $nssmTmp -Filter "nssm.exe" -Recurse |
        Where-Object { $_.FullName -match "win64" } |
        Select-Object -First 1
    if (-not $nssmExe) { Fail "nssm.exe not found in the downloaded archive" }
    Copy-Item -Path $nssmExe.FullName -Destination (Join-Path $Root "dist/UniMonitor/nssm.exe") -Force

    if (Test-Path (Join-Path $Root "INSTALL.md")) {
        Copy-Item -Path (Join-Path $Root "INSTALL.md") -Destination (Join-Path $Root "dist/UniMonitor/INSTALL.md") -Force
    }

    # -- 7. NSIS ---------------------------------------------------------------
    Step "Locating NSIS (makensis)"
    $makensisCandidates = @(
        "C:\Program Files (x86)\NSIS\makensis.exe",
        "C:\Program Files\NSIS\makensis.exe"
    )
    $makensis = $makensisCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $makensis) {
        $makensis = (Get-Command makensis -ErrorAction SilentlyContinue).Source
    }

    if (-not $makensis) {
        Write-Host "NSIS not installed -- installing it for you"
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            & winget install --id NSIS.NSIS --silent --accept-package-agreements --accept-source-agreements
        } elseif (Get-Command choco -ErrorAction SilentlyContinue) {
            & choco install nsis --no-progress -y
        } else {
            Fail "NSIS is missing and neither winget nor choco is available. Install NSIS 3.x from https://nsis.sourceforge.io/Download and re-run."
        }
        $makensis = $makensisCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $makensis) { Fail "NSIS was installed but makensis.exe was not found in the usual folders" }
    }
    Write-Host "Using $makensis"
    Invoke-Checked $makensis @("/VERSION")

    # -- 8. NSIS installer -----------------------------------------------------
    Step "Building the installer"
    Invoke-Checked $makensis @(
        "/V4",
        "/DVERSION=$Version",
        "deploy/windows/install.nsi"
    )
    $installer = Join-Path $Root "dist/UniMonitor-Setup-$Version-x64.exe"
    if (-not (Test-Path $installer)) { Fail "makensis reported success but $installer is missing" }

    # -- 9. Smoke test + portable zip ------------------------------------------
    if (-not $SkipSmokeTest) {
        Step "Smoke-testing the packaged executable"
        $stdout = Join-Path $BuildDir "exe-stdout.txt"
        $stderr = Join-Path $BuildDir "exe-stderr.txt"
        $process = Start-Process -FilePath $exe -ArgumentList "--help" -NoNewWindow -PassThru `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        if (-not $process.WaitForExit(90000)) {
            $process.Kill()
            Fail "UniMonitor.exe --help did not exit within 90 seconds"
        }
        if ($process.ExitCode -ne 0) {
            Get-Content $stderr -ErrorAction SilentlyContinue | Select-Object -First 25
            Fail "UniMonitor.exe --help exited with $($process.ExitCode)"
        }
        if (-not (Select-String -Path $stdout -Pattern "Usage" -Quiet)) {
            Fail "UniMonitor.exe --help produced no usage text"
        }
    }

    Step "Creating the portable zip"
    $portable = Join-Path $Root "dist/UniMonitor-$Version-x64-portable.zip"
    if (Test-Path $portable) { Remove-Item -Force $portable }
    Compress-Archive -Path (Join-Path $Root "dist/UniMonitor/*") -DestinationPath $portable

    $sizeMb = [math]::Round((Get-Item $installer).Length / 1MB, 1)
    Write-Host ""
    Write-Host "Done." -ForegroundColor Green
    Write-Host "  Installer : $installer ($sizeMb MB)"
    Write-Host "  Portable  : $portable"
    Write-Host ""
    Write-Host "Silent install test:" -ForegroundColor Yellow
    Write-Host "  `"$installer`" /S /D=C:\Temp\UniMonitorTest"
}
finally {
    Pop-Location
}
