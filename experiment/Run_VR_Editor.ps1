param([string]$SteamVRManifest)
$ErrorActionPreference = 'Stop'

# Use the same project checks and process-local SteamVR environment as the Demo.
& (Join-Path $PSScriptRoot 'Run_VR_Demo.ps1') -Editor @PSBoundParameters
exit $LASTEXITCODE
