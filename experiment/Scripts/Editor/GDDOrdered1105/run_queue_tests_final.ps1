$ErrorActionPreference='Stop'
$projectRoot='D:\game design\experiment'
$editor='D:\浏览器下载\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$report=Join-Path $projectRoot 'Docs\Gameplay\GDDOrdered1105'
$arguments='"'+(Join-Path $projectRoot 'experiment.uproject')+'" -Unattended -NoSound -NullRHI -nohmd -NoZenAutoLaunch -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="'+(Join-Path $projectRoot 'Saved\BlockoutRuntime\DDC')+'" -ExecCmds="Automation RunTests Nilin.Encounter.StagingQueue" -TestExit="Automation Test Queue Empty" -ReportExportPath="'+(Join-Path $report 'QueueAutomationFinal')+'" -abslog="'+(Join-Path $report 'QueueAutomationFinal.log')+'"'
$process=Start-Process -FilePath $editor -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
[IO.File]::WriteAllText((Join-Path $report 'QueueAutomationFinal.pid'),$process.Id.ToString())
$process | Select-Object Id,ProcessName





