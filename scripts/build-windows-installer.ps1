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
    Expected SHA-256 for the NSSM zip. Defaults to the pinned hash of the
    2.24 release; override only for a different, equally trusted build.

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
# nssm.cc sits behind an nginx that answers 503 often enough that a single
# request is not a reliable build step, and the 503 body still gets written to
# the target file. Retry, then read the same release from the archive mirror.
$NssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$NssmMirrorUrl = "https://web.archive.org/web/2024id_/https://nssm.cc/release/nssm-2.24.zip"
$NssmPinnedSha256 = "727d1e42275c605e0f04aba98095c38a8e1e46def453cdffce42869428aa6743"
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

# Hashing and zipping go through .NET rather than Get-FileHash / Expand-Archive /
# Compress-Archive. Those cmdlets need PowerShell 4+ and the
# Microsoft.PowerShell.Archive module, and on some hosts neither is loadable --
# the build then stopped at "The term 'Get-FileHash' is not recognized". The
# .NET types below ship with every PowerShell that can run this script.
function Get-Sha256([string]$Path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $digest = $sha.ComputeHash($stream)
        return ([System.BitConverter]::ToString($digest) -replace '-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $sha.Dispose()
    }
}

function Import-ZipAssembly {
    # PowerShell 7 already ships the type; Windows PowerShell 5.1 needs the load.
    if (-not ("System.IO.Compression.ZipFile" -as [type])) {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
    }
}

function Expand-Zip([string]$Path, [string]$Destination) {
    Import-ZipAssembly
    if (Test-Path $Destination) { Remove-Item -Recurse -Force $Destination }
    [System.IO.Compression.ZipFile]::ExtractToDirectory($Path, $Destination)
}

function Compress-Zip([string]$Source, [string]$Destination) {
    Import-ZipAssembly
    if (Test-Path $Destination) { Remove-Item -Force $Destination }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($Source, $Destination)
}

function Save-NssmArchive([string]$Path, [string]$ExpectedSha256) {
    # A cached archive that still matches the pin is reused, so a rebuild does
    # not depend on the network. A failed download is discarded rather than
    # left behind as a corrupt zip for Expand-Zip to choke on.
    if (Test-Path $Path) {
        if ((Get-Sha256 $Path) -eq $ExpectedSha256) { return }
        Remove-Item -Force $Path
    }
    foreach ($source in @($NssmUrl, $NssmMirrorUrl)) {
        for ($attempt = 1; $attempt -le 3; $attempt++) {
            try {
                Invoke-WebRequest -Uri $source -OutFile $Path -UseBasicParsing
                if ((Get-Sha256 $Path) -eq $ExpectedSha256) {
                    Write-Host "  downloaded from $source"
                    return
                }
                Write-Host "  $source served an unexpected file" -ForegroundColor Yellow
            } catch {
                Write-Host "  $source attempt $attempt failed: $($_.Exception.Message)" -ForegroundColor Yellow
            }
            if (Test-Path $Path) { Remove-Item -Force $Path }
            if ($attempt -lt 3) { Start-Sleep -Seconds (5 * $attempt) }
        }
    }
    Fail ("NSSM 2.24 could not be downloaded from {0} or its archive mirror. " +
          "Download nssm-2.24.zip by hand, then re-run." -f $NssmUrl)
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
        "-m", "pip", "install", "--no-input", "--no-color",
        "pyinstaller>=6.16.0,<7",
        "-e", ".[production]"
    )
    # pip can exit 0 without putting PyInstaller in this environment (a PIP_TARGET
    # or PIP_PREFIX setting, a stray PYTHONPATH, an install that hit another
    # interpreter). Trust the postcondition, not the exit code.
    $pyinstallerVersion = & $VenvPython -c "import PyInstaller; print(PyInstaller.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $pyinstallerVersion) {
        Fail ("PyInstaller is not importable from {0}. Run '{0} -m pip config list' and check for " +
              "PIP_TARGET, PIP_PREFIX or PYTHONPATH, or delete .build-venv and re-run." -f $VenvPython)
    }
    Write-Host "  PyInstaller $pyinstallerVersion"

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
        "-m", "PyInstaller",
        "deploy/windows/unimonitor.spec",
        "--clean", "--noconfirm"
    )
    $exe = Join-Path $Root "dist/UniMonitor/UniMonitor.exe"
    if (-not (Test-Path $exe)) { Fail "PyInstaller finished but dist/UniMonitor/UniMonitor.exe is missing" }

    # -- 6. NSSM (Windows service helper) --------------------------------------
    Step "Fetching NSSM"
    New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
    $zip = Join-Path $BuildDir "nssm.zip"
    $expectedNssmHash = if ($NssmSha256) { $NssmSha256.ToLowerInvariant() } else { $NssmPinnedSha256 }
    Save-NssmArchive $zip $expectedNssmHash
    Write-Host "NSSM SHA256 $(Get-Sha256 $zip)"
    $nssmTmp = Join-Path $BuildDir "nssm"
    Expand-Zip -Path $zip -Destination $nssmTmp
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
        # Not Start-Process: on PowerShell 7 a -PassThru process started with
        # -NoNewWindow and redirection reports a $null ExitCode (PowerShell issue
        # #20400), and $null -ne 0 is true -- so a healthy exe was reported as
        # "exited with" no code and no output. A plain .NET process reads the real
        # exit code, and both streams are printed when it does fail.
        $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
        $startInfo.FileName = $exe
        $startInfo.Arguments = "--help"
        $startInfo.WorkingDirectory = Split-Path -Parent $exe
        $startInfo.UseShellExecute = $false
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $smoke = [System.Diagnostics.Process]::Start($startInfo)
        # Read both streams while the exe runs, so a full pipe buffer cannot block it.
        $smokeOut = $smoke.StandardOutput.ReadToEndAsync()
        $smokeErr = $smoke.StandardError.ReadToEndAsync()
        if (-not $smoke.WaitForExit(90000)) {
            $smoke.Kill()
            Fail "UniMonitor.exe --help did not exit within 90 seconds"
        }
        $stdoutText = $smokeOut.GetAwaiter().GetResult()
        $stderrText = $smokeErr.GetAwaiter().GetResult()
        Set-Content -Path (Join-Path $BuildDir "exe-stdout.txt") -Value $stdoutText
        Set-Content -Path (Join-Path $BuildDir "exe-stderr.txt") -Value $stderrText
        if ($smoke.ExitCode -ne 0) {
            Write-Host "--- UniMonitor.exe --help stdout ---"
            Write-Host $stdoutText
            Write-Host "--- UniMonitor.exe --help stderr ---"
            Write-Host $stderrText
            Fail "UniMonitor.exe --help exited with $($smoke.ExitCode)"
        }
        if ($stdoutText -notmatch "Usage") {
            Fail "UniMonitor.exe --help produced no usage text"
        }
    }

    Step "Creating the portable zip"
    $portable = Join-Path $Root "dist/UniMonitor-$Version-x64-portable.zip"
    if (Test-Path $portable) { Remove-Item -Force $portable }
    Compress-Zip -Source (Join-Path $Root "dist/UniMonitor") -Destination $portable

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
