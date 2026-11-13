@echo off
powershell.exe -NoProfile -File "%~dp0Run_CombatLab_Demo.ps1"
if errorlevel 1 pause
