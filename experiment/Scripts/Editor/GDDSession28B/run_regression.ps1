$ErrorActionPreference='Stop'
$projectRoot='D:\game design\experiment'
$editor='D:\浏览器下载\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$report=Join-Path $projectRoot 'Docs\Gameplay\GDDSession28B'
$arguments='"'+(Join-Path $projectRoot 'experiment.uproject')+'" -Unattended -NoSound -NullRHI -nohmd -NoZenAutoLaunch -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="'+(Join-Path $projectRoot 'Saved\BlockoutRuntime\DDC')+'" -ExecCmds="Automation RunTests Nilin." -TestExit="Automation Test Queue Empty" -ReportExportPath="'+(Join-Path $report 'Automation_01')+'" -abslog="'+(Join-Path $report 'Automation_01.log')+'"'
$process=Start-Process -FilePath $editor -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
[IO.File]::WriteAllText((Join-Path $report 'Automation.pid'),$process.Id.ToString())
$process | Select-Object Id,ProcessName
