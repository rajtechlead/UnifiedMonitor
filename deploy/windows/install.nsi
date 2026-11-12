; ============================================================
; UniMonitor Windows Installer — NSIS Script
; ============================================================
; Requirements:
;   NSIS 3.x (https://nsis.sourceforge.io/)
;   The dist/UniMonitor/ folder produced by PyInstaller
;
; Build:
;   makensis /DVERSION=1.0.0 deploy/windows/install.nsi
;
; Output: dist/UniMonitor-Setup-1.0.0-x64.exe
; ============================================================

!define APPNAME      "UniMonitor"
!define APPVERSION   "1.0.0"
!define PUBLISHER    "rajtechlead"
!define WEBSITE      "https://github.com/rajtechlead/UniMonitor"
!define CONTACT      "rajrsngroup@gmail.com"
!define DESCRIPTION  "Unified M365 Security Monitoring & GRC Platform"
!define INSTALL_DIR  "$PROGRAMFILES64\${APPNAME}"
!define REG_KEY      "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APPNAME}"
!define SERVICE_NAME "UniMonitor"
!define SERVICE_PORT "8000"

; Allow version override from command line: /DVERSION=x.y.z
!ifdef VERSION
  !undef APPVERSION
  !define APPVERSION "${VERSION}"
!endif

; ── NSIS settings ─────────────────────────────────────────────────────────────
Unicode True
SetCompressor /SOLID lzma
RequestExecutionLevel admin
InstallDir     "${INSTALL_DIR}"
Name           "${APPNAME} ${APPVERSION}"
OutFile        "..\..\dist\UniMonitor-Setup-${APPVERSION}-x64.exe"
BrandingText   "${APPNAME} ${APPVERSION} — ${PUBLISHER}"

; Modern UI
!include "MUI2.nsh"
!include "x64.nsh"
!include "LogicLib.nsh"
!include "WinMessages.nsh"
!include "nsDialogs.nsh"

; MUI configuration
!define MUI_ABORTWARNING
!define MUI_ICON          "..\..\branding\icon.ico"
!define MUI_UNICON        "..\..\branding\icon.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_WELCOMEPAGE_TITLE  "Welcome to ${APPNAME} Setup"
!define MUI_WELCOMEPAGE_TEXT   "This wizard will install ${APPNAME} ${APPVERSION} on your computer.$\r$\n$\r$\nUniMonitor provides unified Microsoft 365 security monitoring, GRC framework assessments, and compliance reporting.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT   "Open UniMonitor in browser (http://localhost:${SERVICE_PORT})"
!define MUI_FINISHPAGE_RUN_FUNCTION FinishPageAction
!define MUI_FINISHPAGE_SHOWREADME
!define MUI_FINISHPAGE_SHOWREADME_TEXT  "Show installation guide"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION ShowReadme

; ── Pages ──────────────────────────────────────────────────────────────────────
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

; ── Version information (embedded in PE header) ────────────────────────────────
VIProductVersion "${APPVERSION}.0"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductName"      "${APPNAME}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "CompanyName"      "${PUBLISHER}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "LegalCopyright"   "Copyright © 2024 ${PUBLISHER}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileDescription"  "${DESCRIPTION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "FileVersion"      "${APPVERSION}"
VIAddVersionKey /LANG=${LANG_ENGLISH} "ProductVersion"   "${APPVERSION}"

; ── Component descriptions ─────────────────────────────────────────────────────
InstType "Full"
InstType "Minimal (no Windows Service)"

SectionGroup "Core" SecCore
  Section "UniMonitor Application" SecApp
    SectionIn RO  ; required, cannot be deselected
    AddSize 150000  ; ~150 MB estimate

    SetOutPath "$INSTDIR"
    SetOverwrite on

    ; Install all files from the PyInstaller dist folder
    File /r "..\..\dist\UniMonitor\*.*"

    ; Write uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Write registry keys for Add/Remove Programs
    WriteRegStr   HKLM "${REG_KEY}" "DisplayName"      "${APPNAME} ${APPVERSION}"
    WriteRegStr   HKLM "${REG_KEY}" "DisplayVersion"   "${APPVERSION}"
    WriteRegStr   HKLM "${REG_KEY}" "Publisher"        "${PUBLISHER}"
    WriteRegStr   HKLM "${REG_KEY}" "URLInfoAbout"     "${WEBSITE}"
    WriteRegStr   HKLM "${REG_KEY}" "Contact"          "${CONTACT}"
    WriteRegStr   HKLM "${REG_KEY}" "InstallLocation"  "$INSTDIR"
    WriteRegStr   HKLM "${REG_KEY}" "UninstallString"  '"$INSTDIR\Uninstall.exe"'
    WriteRegStr   HKLM "${REG_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegDWORD HKLM "${REG_KEY}" "NoModify"         1
    WriteRegDWORD HKLM "${REG_KEY}" "NoRepair"         1

    ; Add to PATH
    EnVar::AddValue "PATH" "$INSTDIR"
    Pop $0

    ; Write a default .env if it doesn't exist
    ${IfNot} ${FileExists} "$INSTDIR\.env"
      FileOpen  $0 "$INSTDIR\.env" w
      FileWrite $0 "# UniMonitor configuration$\r$\n"
      FileWrite $0 "# Edit these values before starting UniMonitor$\r$\n"
      FileWrite $0 "$\r$\n"
      FileWrite $0 "UNIMONITOR_ENV=production$\r$\n"
      FileWrite $0 "DATABASE_URL=sqlite+aiosqlite:///C:/ProgramData/UniMonitor/unimonitor.db$\r$\n"
      FileWrite $0 "REDIS_URL=redis://localhost:6379/0$\r$\n"
      FileWrite $0 "SECRETS_PROVIDER=local$\r$\n"
      FileWrite $0 "UNIMONITOR_SECRET_KEY=$\r$\n"
      FileWrite $0 "# Generate a secret key: UniMonitor.exe genkey$\r$\n"
      FileClose $0
    ${EndIf}

    ; Create ProgramData directory for data files
    CreateDirectory "C:\ProgramData\UniMonitor"
    CreateDirectory "C:\ProgramData\UniMonitor\reports"
    CreateDirectory "C:\ProgramData\UniMonitor\logs"

  SectionEnd
SectionGroupEnd

Section "Windows Service (auto-start)" SecService
  SectionIn 1  ; Full install only
  AddSize 100

  ; Register as a Windows service using NSSM (if present) or sc.exe
  ; UniMonitor ships a bundled NSSM binary
  ${If} ${FileExists} "$INSTDIR\nssm.exe"
    ExecWait '"$INSTDIR\nssm.exe" install "${SERVICE_NAME}" "$INSTDIR\UniMonitor.exe" "start --host 0.0.0.0 --port ${SERVICE_PORT}"'
    ExecWait '"$INSTDIR\nssm.exe" set "${SERVICE_NAME}" AppDirectory "$INSTDIR"'
    ExecWait '"$INSTDIR\nssm.exe" set "${SERVICE_NAME}" AppEnvironmentExtra "UNIMONITOR_ENV=production"'
    ExecWait '"$INSTDIR\nssm.exe" set "${SERVICE_NAME}" Description "${DESCRIPTION}"'
    ExecWait '"$INSTDIR\nssm.exe" set "${SERVICE_NAME}" Start SERVICE_AUTO_START'
    ExecWait '"$INSTDIR\nssm.exe" start "${SERVICE_NAME}"'
  ${Else}
    ; Fallback: create a startup shortcut in the Startup folder
    CreateShortcut "$SMSTARTUP\${APPNAME}.lnk" "$INSTDIR\UniMonitor.exe" \
      "start --host 0.0.0.0 --port ${SERVICE_PORT}" "$INSTDIR\UniMonitor.exe" 0
  ${EndIf}
SectionEnd

Section "Start Menu Shortcuts" SecShortcuts
  SectionIn 1 2
  CreateDirectory "$SMPROGRAMS\${APPNAME}"
  CreateShortcut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" \
    "$INSTDIR\UniMonitor.exe" "start" "$INSTDIR\UniMonitor.exe" 0
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Open in Browser.lnk" \
    "http://localhost:${SERVICE_PORT}" "" "" 0
  CreateShortcut "$SMPROGRAMS\${APPNAME}\Uninstall.lnk" \
    "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0
  CreateShortcut "$DESKTOP\${APPNAME}.lnk" \
    "$INSTDIR\UniMonitor.exe" "start" "$INSTDIR\UniMonitor.exe" 0
SectionEnd

; ── Section descriptions (shown in component page tooltip) ────────────────────
LangString DESC_SecApp       ${LANG_ENGLISH} "UniMonitor application and all runtime dependencies. Required."
LangString DESC_SecService   ${LANG_ENGLISH} "Register UniMonitor as a Windows Service that starts automatically. Requires admin privileges."
LangString DESC_SecShortcuts ${LANG_ENGLISH} "Add Start Menu and Desktop shortcuts."

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecApp}       $(DESC_SecApp)
  !insertmacro MUI_DESCRIPTION_TEXT ${SecService}   $(DESC_SecService)
  !insertmacro MUI_DESCRIPTION_TEXT ${SecShortcuts} $(DESC_SecShortcuts)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ── Finish page actions ────────────────────────────────────────────────────────
Function FinishPageAction
  ExecShell "open" "http://localhost:${SERVICE_PORT}"
FunctionEnd

Function ShowReadme
  ExecShell "open" "$INSTDIR\INSTALL.md"
FunctionEnd

; ── Uninstaller ───────────────────────────────────────────────────────────────
Section "Uninstall"
  ; Stop and remove service
  ${If} ${FileExists} "$INSTDIR\nssm.exe"
    ExecWait '"$INSTDIR\nssm.exe" stop "${SERVICE_NAME}"'
    ExecWait '"$INSTDIR\nssm.exe" remove "${SERVICE_NAME}" confirm'
  ${Else}
    ExecWait 'sc stop "${SERVICE_NAME}"'
    ExecWait 'sc delete "${SERVICE_NAME}"'
  ${EndIf}

  ; Remove from PATH
  EnVar::DeleteValue "PATH" "$INSTDIR"
  Pop $0

  ; Remove files
  RMDir /r "$INSTDIR"

  ; Remove shortcuts
  Delete "$DESKTOP\${APPNAME}.lnk"
  RMDir /r "$SMPROGRAMS\${APPNAME}"
  Delete "$SMSTARTUP\${APPNAME}.lnk"

  ; Remove registry keys
  DeleteRegKey HKLM "${REG_KEY}"

  ; Note: C:\ProgramData\UniMonitor (data/logs) is intentionally kept
  MessageBox MB_OK "UniMonitor has been uninstalled.$\r$\nYour data at C:\ProgramData\UniMonitor has been preserved."
SectionEnd
