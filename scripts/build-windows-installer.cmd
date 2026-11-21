@echo off
REM One-command Windows installer build. Passes any arguments through,
REM e.g. build-windows-installer.cmd -Version 1.2.0
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-windows-installer.ps1" %*
exit /b %ERRORLEVEL%
