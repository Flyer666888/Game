@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Open_Enemy_Rig_Editor.ps1"
if errorlevel 1 (
    pause
    exit /b 1
)
exit /b 0
