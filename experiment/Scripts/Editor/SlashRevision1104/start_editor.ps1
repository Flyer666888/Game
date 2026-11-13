$ErrorActionPreference='Stop'
$projectRoot='D:\game design\experiment'
$editor='D:\浏览器下载\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$report=Join-Path $projectRoot 'Docs\Gameplay\SlashRevision1104'
$arguments='"'+(Join-Path $projectRoot 'experiment.uproject')+'" /Game/ReversedScale/Maps/L_CombatLabVR -windowed -ResX=1280 -ResY=900 -ForceRes -RenderOffScreen -nohmd -unattended -nosplash -nosound -NoZenAutoLaunch -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="'+(Join-Path $projectRoot 'Saved\BlockoutRuntime\DDC')+'" -ShaderWorkingDir="'+(Join-Path $projectRoot 'Saved\BlockoutRuntime\ShaderWorkingDir')+'" -ExecCmds="py D:/game design/experiment/Scripts/Editor/SlashRevision1104/review_session.py" -abslog="'+(Join-Path $report 'Editor.log')+'"'
$process=Start-Process -FilePath $editor -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
[IO.File]::WriteAllText((Join-Path $report 'Editor.pid'),$process.Id.ToString())
$process | Select-Object Id,ProcessName

