param([ValidateSet('V06','V07','V08','V09')][string]$MapVersion = 'V09')
$ErrorActionPreference = 'Stop'
$ueEditor = 'D:\浏览器下载\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$uproject = Join-Path $PSScriptRoot 'experiment.uproject'
$map = '/Game/ReversedScale/Maps/L_NilinBlockout' + $MapVersion
$mapFile = Join-Path $PSScriptRoot ('Content\ReversedScale\Maps\L_NilinBlockout' + $MapVersion + '.umap')
foreach ($required in @($ueEditor, $uproject, $mapFile)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Required file missing: $required" }
}
$runtime = Join-Path $PSScriptRoot 'Saved\BlockoutRuntime'
$ddc = Join-Path $runtime 'DDC'
$shader = Join-Path $runtime 'ShaderWorkingDir'
$logs = Join-Path $runtime 'Logs'
foreach ($directory in @($ddc, $shader, $logs)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
$log = Join-Path $logs ('BlockoutEditor_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.log')
$arguments = '"' + $uproject + '" ' + $map +
    ' -NoZenAutoLaunch -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="' + $ddc +
    '" -ShaderWorkingDir="' + $shader +
    '" -EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities -nohmd -unattended -windowed -ResX=1600 -ResY=900 -abslog="' + $log + '"'
Start-Process -FilePath $ueEditor -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -WindowStyle Normal -PassThru |
    Select-Object Id, ProcessName
