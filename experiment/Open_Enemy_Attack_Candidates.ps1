$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$editor = Join-Path $projectRoot 'Saved\BuildRuntime\UE58\Engine\Binaries\Win64\UnrealEditor.exe'
$projectFile = Join-Path $projectRoot 'experiment.uproject'
$startup = Join-Path $projectRoot 'Scripts\Editor\PackSlashReview1104\open_candidates_for_user.py'
foreach ($required in @($editor, $projectFile, $startup)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing required file: $required" }
}
$arguments = '"' + $projectFile + '" /Game/ReversedScale/Maps/L_CombatLabVR -nohmd -nosplash -NoZenAutoLaunch -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="' + (Join-Path $projectRoot 'Saved\BlockoutRuntime\DDC') + '" -ShaderWorkingDir="' + (Join-Path $projectRoot 'Saved\BlockoutRuntime\ShaderWorkingDir') + '" -ExecCmds="py ' + $startup.Replace('\','/') + '" -abslog="' + (Join-Path $projectRoot 'Docs\Gameplay\PackSlashReview1104\UserCandidateEditor.log') + '"'
Start-Process -FilePath $editor -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Normal
