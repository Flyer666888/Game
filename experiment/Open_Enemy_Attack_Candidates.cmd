@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Open_Enemy_Attack_Candidates.ps1"
if errorlevel 1 pause
