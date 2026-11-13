@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run_RitualObjective_Demo.ps1"
if errorlevel 1 pause
