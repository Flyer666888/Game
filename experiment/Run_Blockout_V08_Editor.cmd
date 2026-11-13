@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run_Blockout_Editor.ps1" -MapVersion V08
exit /b %errorlevel%
