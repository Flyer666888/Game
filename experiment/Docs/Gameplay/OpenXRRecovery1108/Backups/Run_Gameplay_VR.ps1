param([string]$SteamVRManifest, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
# Standalone main-level route; the URL selects the VR GameMode for this process.
& (Join-Path $PSScriptRoot 'Run_VR_Demo.ps1') @PSBoundParameters -MainLevel
exit $LASTEXITCODE
