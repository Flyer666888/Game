@echo off
rem ============================================================
rem  Node.js One-Click Installer
rem  ------------------------------------------------------------
rem  This file is pure English / ASCII on purpose:
rem  Windows reads .bat files with the system ANSI codepage and
rem  non-ASCII text can break the script.
rem
rem  WHAT IT DOES
rem   1. If Node.js is already installed, it says so and stops.
rem   2. Otherwise it installs Node.js LTS, trying in this order:
rem        a) a node-vXXX-x64.msi file placed in this folder
rem           (works on a PC WITHOUT internet),
rem        b) winget, the built-in Windows package manager,
rem        c) downloading the official MSI from nodejs.org.
rem   3. It verifies the installation at the end.
rem
rem  HOW TO USE: double-click this file, then click YES when
rem  Windows asks for permission. Wait 1-3 minutes.
rem
rem  OFFLINE USE: on any PC with internet, download the Node.js
rem  "Windows Installer .msi 64-bit" from https://nodejs.org,
rem  put that .msi file in THIS folder, and copy this whole
rem  folder to the offline PC.
rem ============================================================
setlocal EnableExtensions
title Node.js One-Click Installer
cd /d "%~dp0"

echo ============================================================
echo   Node.js One-Click Installer
echo   For the Camera Interactive Class web app
echo ============================================================
echo.

rem ------------------------------------------------------------
rem Step 0: nothing to do if Node.js already works
rem ------------------------------------------------------------
where node >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] Node.js is already installed:
    node --version
    echo.
    echo Nothing to do. Close this window and double-click the
    echo app launcher instead.
    pause
    exit /b 0
)

echo [INFO] Node.js is not installed on this computer yet.
echo.

rem ------------------------------------------------------------
rem Step 1: get administrator rights - installing needs them
rem ------------------------------------------------------------
net session >nul 2>nul
if %errorlevel% equ 0 goto :admin
echo [INFO] Administrator permission is required.
echo [INFO] When the permission window pops up, click YES.
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>nul
echo.
echo [INFO] If you clicked NO just now, run this file again and click YES.
timeout /t 5 >nul
exit /b

:admin
cd /d "%~dp0"

rem ------------------------------------------------------------
rem Step 2a: try winget first (built into Windows 10/11)
rem ------------------------------------------------------------
echo [STEP 1/3] Trying winget, the built-in Windows installer...
where winget >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] winget is not available on this PC.
    goto :download
)
winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements --silent
if %errorlevel% equ 0 goto :check
echo [WARN] winget did not work. Trying direct download instead...

rem ------------------------------------------------------------
rem Step 2b: use a bundled MSI, or download one from nodejs.org
rem ------------------------------------------------------------
:download
echo.
echo [STEP 2/3] Getting the Node.js installer...
set "MSI="
rem If a Node.js MSI was placed in this folder, use it - works offline.
for %%f in ("%~dp0node-v*-x64.msi") do set "MSI=%%~ff"
if defined MSI goto :install
set "MSI=%TEMP%\nodejs-lts-installer.msi"
set "DOWNLOADED=1"
echo [INFO] Downloading the official Node.js LTS installer...
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $r=Invoke-RestMethod 'https://nodejs.org/dist/index.json'; $v=($r | Where-Object { $_.lts } | Select-Object -First 1).version; Write-Host ('[INFO] Latest LTS version: ' + $v); Invoke-WebRequest -Uri ('https://nodejs.org/dist/' + $v + '/node' + $v + '-x64.msi') -OutFile '%MSI%' -UseBasicParsing"
if exist "%MSI%" goto :install
echo.
echo [ERROR] The download failed. Two options:
echo   1. Check the internet connection, then run this file again.
echo   2. On any PC with internet, download the Node.js
echo      "Windows Installer .msi 64-bit" from https://nodejs.org,
echo      copy the .msi into THIS folder, and run this file again.
pause
exit /b 1

rem ------------------------------------------------------------
rem Step 3: run the installer
rem ------------------------------------------------------------
:install
echo.
echo [STEP 3/3] Installing Node.js. Please wait 1-3 minutes...
echo            Do NOT close this window.
msiexec /i "%MSI%" /qn /norestart
if %errorlevel% equ 0 goto :cleanup
if %errorlevel% equ 3010 goto :cleanup
echo [WARN] The quiet install did not finish by itself.
echo        Opening the installer window now - click Next, Next,
echo        then Install until it is done.
msiexec /i "%MSI%"

:cleanup
if defined DOWNLOADED del "%MSI%" >nul 2>nul

rem ------------------------------------------------------------
rem Step 4: verify
rem ------------------------------------------------------------
:check
echo.
echo [CHECK] Verifying the installation...
set "PATH=%PATH%;C:\Program Files\nodejs"
where node >nul 2>nul
if %errorlevel% equ 0 goto :done
echo.
echo [ERROR] Node.js is still not recognized.
echo If it was just installed, restart the computer and then
echo double-click the app launcher again.
pause
exit /b 1

:done
echo.
echo ============================================================
echo   [OK] Node.js is installed and ready:
node --version
echo.
echo   Close this window, then double-click the app launcher
echo   to start the class app.
echo ============================================================
pause
exit /b 0
