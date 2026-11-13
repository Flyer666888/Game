@echo off
rem ============================================================
rem  Camera Interactive Class - One-Click Launcher
rem ------------------------------------------------------------
rem  WHY THIS FILE IS ALL IN ENGLISH:
rem  Windows reads .cmd files with the system ANSI codepage
rem  (GBK on Chinese Windows). Chinese text saved as UTF-8 gets
rem  garbled or even breaks the script. So every character in
rem  this file is plain ASCII. Chinese instructions: README.md
rem
rem  WHAT IT DOES
rem   1. If port 8000 is held by an OLD python/node server
rem      (leftover from a previous run of this launcher),
rem      close it automatically.
rem      Other programs on the port (editors, dev tools...) are
rem      NOT touched - killing them could lose your work. In that
rem      case the launcher automatically picks a free port instead.
rem      (Set FORCE_KILL=1 below to kill ANY process on the port.)
rem   2. Start a tiny local web server.
rem   3. Open the browser at the menu page.
rem
rem  A local server is REQUIRED: browsers only allow camera access
rem  on http://localhost pages, never on file:// pages.
rem
rem  HOW TO USE: double-click this file.
rem  Keep this window open during class; close it to stop.
rem ============================================================
chcp 65001 >nul
title Camera Class Server - keep this window open!
cd /d "%~dp0"

rem ------------------------------------------------------------
rem Guard: make sure we run from the FULLY EXTRACTED folder.
rem Double-clicking this file INSIDE the .zip makes Windows
rem extract ONLY this .cmd to a temp folder, where server.js
rem and the web pages are missing -> confusing errors later.
rem ------------------------------------------------------------
if exist "%~dp0server.js" goto :fileok
echo [ERROR] server.js was not found next to this launcher.
echo.
echo This usually means the launcher was started INSIDE the zip.
echo Please do this instead:
echo    1. Right-click the .zip file and choose "Extract All...".
echo    2. Open the extracted folder.
echo    3. Double-click this launcher again from that folder.
echo.
pause
goto :eof
:fileok

rem Set to 1 to force-close ANY process holding the port (dangerous)
set FORCE_KILL=0

set PORT=8000

echo ============================================================
echo   Camera Interactive Class - starting...
echo ============================================================
echo.

rem ------------------------------------------------------------
rem Step 1: close our own leftover servers on the port
rem ------------------------------------------------------------
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r /c:":%PORT% .*LISTENING"') do call :freeifours %%a

rem ------------------------------------------------------------
rem Step 2: if the port is still busy, pick a free port instead
rem ------------------------------------------------------------
call :checkfree %PORT%
if not errorlevel 1 goto :portok
echo [WARN ] Port %PORT% is held by ANOTHER program, we will not kill it.
:findport
set /a PORT+=1
call :checkfree %PORT%
if errorlevel 1 (
    if %PORT% LSS 8020 goto :findport
    echo [ERROR] No free port found between 8001-8020.
    pause
    goto :eof
)
echo [INFO ] Using port %PORT% instead.
:portok
set URL=http://localhost:%PORT%/index.html
echo.
echo   Address: %URL%
echo   Keep this window OPEN during class.
echo   Closing this window = stopping the server.
echo.
echo   Browser tips: click ALLOW when asked for camera permission.
echo.

rem ------------------------------------------------------------
rem Step 3: start the server (Python first, Node.js as backup)
rem ------------------------------------------------------------
python --version >nul 2>nul
if not errorlevel 1 (
    echo [SERVER] Python
    start "" %URL%
    python -m http.server %PORT%
    goto :end
)

py -3 --version >nul 2>nul
if not errorlevel 1 (
    echo [SERVER] Python ^(py^)
    start "" %URL%
    py -3 -m http.server %PORT%
    goto :end
)

node --version >nul 2>nul
if not errorlevel 1 (
    echo [SERVER] Node.js
    start "" %URL%
    node server.js %PORT%
    goto :end
)

echo [ERROR] Neither Python nor Node.js was found on this computer.
echo Easiest fix - double-click this installer and click YES:
echo    install-nodejs\install-nodejs.bat
echo Or install one of them yourself first:
echo    Python : https://www.python.org/downloads/   (tick "Add to PATH")
echo    Node.js: https://nodejs.org/en
echo Then double-click this file again.
echo.
pause
goto :eof

rem ============================================================
rem Subroutines
rem ============================================================

rem :freeifours  <pid>
rem Closes the process ONLY if it is a python/node server
rem (i.e. a leftover from a previous run of this launcher).
rem Anything else is left alone to protect unsaved work.
:freeifours
if "%FORCE_KILL%"=="1" goto :dozan
set PROCNAME=
for /f "tokens=1" %%n in ('tasklist /fi "PID eq %1" /nh 2^>nul ^| findstr /i "exe"') do if not defined PROCNAME set PROCNAME=%%n
echo Port %PORT% busy: PID %1 (%PROCNAME%)
if /i "%PROCNAME%"=="python.exe"   goto :dozan
if /i "%PROCNAME%"=="pythonw.exe"  goto :dozan
if /i "%PROCNAME%"=="node.exe"     goto :dozan
echo   ...not one of our servers, leave it alone.
goto :eof
:dozan
echo   ...old leftover server, closing it.
taskkill /F /PID %1 >nul 2>&1
goto :eof

rem :checkfree  <port>
rem Sets ERRORLEVEL 0 if the port is free, 1 if it is in use.
:checkfree
netstat -ano | findstr /r /c:":%1 .*LISTENING" >nul 2>&1
if errorlevel 1 exit /b 0
exit /b 1

:end
echo.
echo Server stopped. Bye!
pause
