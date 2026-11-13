@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run_Blockout_Demo.ps1" -MapVersion V07
exit /b %errorlevel%
