param()
$ErrorActionPreference='Stop'
$ueEditor='D:\浏览器下载\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$uproject=Join-Path $PSScriptRoot 'experiment.uproject'
$map='/Game/ReversedScale/Maps/L_NilinGameplayV01'
$mapFile=Join-Path $PSScriptRoot 'Content\ReversedScale\Maps\L_NilinGameplayV01.umap'
foreach($file in @($ueEditor,$uproject,$mapFile)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){throw "Required file missing: $file"}
}
$runtime=Join-Path $PSScriptRoot 'Saved\BlockoutRuntime'
$logs=Join-Path $PSScriptRoot 'Saved\GameplayRuntime\Logs'
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$log=Join-Path $logs ('Gameplay_'+(Get-Date -Format 'yyyyMMdd_HHmmss_fff')+'.log')
$arguments='"'+$uproject+'" '+$map+' -game -nohmd -windowed -ResX=1600 -ResY=900 -unattended -NoZenAutoLaunch -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="'+(Join-Path $runtime 'DDC')+'" -ShaderWorkingDir="'+(Join-Path $runtime 'ShaderWorkingDir')+'" -ExecCmds="t.MaxFPS 60" -abslog="'+$log+'"'
Start-Process -FilePath $ueEditor -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Normal -PassThru | Select-Object Id,ProcessName
