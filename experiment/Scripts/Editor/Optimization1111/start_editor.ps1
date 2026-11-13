$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
if (Get-Process UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue) {
    throw 'An Unreal process already exists. Inspect its ownership before continuing.'
}
$editor = Join-Path $projectRoot 'Saved\BuildRuntime\UE58\Engine\Binaries\Win64\UnrealEditor.exe'
$worker = (Join-Path $PSScriptRoot 'review_session.py').Replace('\','/')
$log = Join-Path $projectRoot ('Saved\Logs\Optimization1111_Editor_'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.log')
$arguments = '"'+(Join-Path $projectRoot 'experiment.uproject')+'" /Game/ReversedScale/Maps/L_CombatLabVR -windowed -ResX=1600 -ResY=900 -ForceRes -RenderOffScreen -nohmd -unattended -nosplash -nosound -NoLiveCoding -NoZenAutoLaunch -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="'+(Join-Path $projectRoot 'Saved\VRRuntime\DDC')+'" -ShaderWorkingDir="'+(Join-Path $projectRoot 'Saved\VRRuntime\ShaderWorkingDir')+'" -ExecCmds="py '+$worker+'" -abslog="'+$log+'"'
$process = Start-Process -FilePath $editor -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
[pscustomobject]@{ProcessId=$process.Id;StartedAt=[DateTimeOffset]::Now.ToString('o');Log=$log;Worker=$worker} |
    ConvertTo-Json | Tee-Object -LiteralPath (Join-Path $projectRoot 'Docs\Gameplay\Optimization1111\EditorLaunch.json')
