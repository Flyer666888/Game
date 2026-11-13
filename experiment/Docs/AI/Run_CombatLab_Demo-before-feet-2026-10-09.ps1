param([switch]$CaptureScreenshot)
$ueEditor = 'D:\浏览器下载\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$uproject = Join-Path $PSScriptRoot 'experiment.uproject'
$map = '/Game/ReversedScale/Maps/L_CombatLabWuxiaFace'
$shaderWorkingDir = 'C:\Users\21475\.codex\visualizations\2026\10\01\01a0f77b-1abb-70a0-9543-7d60afd089de\ShaderWorkingDir'
if (-not (Test-Path -LiteralPath $ueEditor)) { throw "找不到 UE 5.8 编辑器：$ueEditor" }
if (-not (Test-Path -LiteralPath $uproject)) { throw "找不到项目文件：$uproject" }
$ddcPath = Join-Path (Split-Path $shaderWorkingDir -Parent) 'DDC'
New-Item -ItemType Directory -Path $ddcPath -Force | Out-Null
$previewLog = Join-Path $PSScriptRoot 'Saved\Logs\DesktopPreview.log'
$arguments = '"' + $uproject + '" ' + $map + ' -game -windowed -ResX=1600 -ResY=900 -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="' + $ddcPath + '" -NoZenAutoLaunch -ShaderWorkingDir="' + $shaderWorkingDir + '" -nohmd -unattended -abslog="' + $previewLog + '"'
if ($CaptureScreenshot) {
    $captureScript = Join-Path (Split-Path $shaderWorkingDir -Parent) 'capture_preview.py'
    $arguments += ' -ExecCmds="py ' + $captureScript + '"'
}
Start-Process -FilePath $ueEditor -ArgumentList $arguments -WorkingDirectory $PSScriptRoot -PassThru | Select-Object Id,ProcessName
