@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build_CombatModule.ps1" %*
set "BUILD_EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %BUILD_EXIT_CODE%
