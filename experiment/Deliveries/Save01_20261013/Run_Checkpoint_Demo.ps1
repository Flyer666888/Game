param([switch]$CaptureScreenshot)
$ErrorActionPreference = 'Stop'
$ueEditor = 'D:\浏览器下载\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$taskCache = 'C:\Users\21475\.codex\visualizations\2026\10\01\01a0f77b-1abb-70a0-9543-7d60afd089de'
$projectCache = Join-Path $taskCache 'CombatProject'
$physicalProject = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
$physicalUproject = Join-Path $physicalProject 'experiment.uproject'
$map = '/Game/ReversedScale/Maps/L_CombatLabCheckpoint'
if (-not (Test-Path -LiteralPath $ueEditor)) { throw "找不到 UE 5.8 编辑器：$ueEditor" }
if (-not (Test-Path -LiteralPath $physicalUproject)) { throw "找不到项目文件：$physicalUproject" }
New-Item -ItemType Directory -Path $taskCache -Force | Out-Null
if (Test-Path -LiteralPath $projectCache) {
    $existingCache = Get-Item -LiteralPath $projectCache -Force
    if (($existingCache.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) {
        throw "ASCII 项目路径已被普通目录占用：$projectCache"
    }
    $rawTarget = [string](@($existingCache.Target)[0])
    $existingTarget = [IO.Path]::GetFullPath($rawTarget).TrimEnd('\')
    if ($existingTarget -ine $physicalProject) {
        throw "ASCII 项目链接指向另一个目录：$existingTarget"
    }
} else {
    New-Item -ItemType Junction -Path $projectCache -Target $physicalProject | Out-Null
}
$uproject = Join-Path $projectCache 'experiment.uproject'
$shaderWorkingDir = Join-Path $taskCache 'ShaderWorkingDir'
$ddcPath = Join-Path $taskCache 'DDC'
$logDirectory = Join-Path $projectCache 'Saved\Logs'
New-Item -ItemType Directory -Path $shaderWorkingDir -Force | Out-Null
New-Item -ItemType Directory -Path $ddcPath -Force | Out-Null
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
$previewLog = Join-Path $logDirectory 'CheckpointPreview.log'
$arguments = '"' + $uproject + '" ' + $map + ' -game -windowed -ResX=1600 -ResY=900 -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="' + $ddcPath + '" -NoZenAutoLaunch -ShaderWorkingDir="' + $shaderWorkingDir + '" -nohmd -unattended -abslog="' + $previewLog + '"'
if ($CaptureScreenshot) {
    $captureScript = Join-Path $projectCache 'Saved\Scripts\capture_checkpoint_lab.py'
    if (-not (Test-Path -LiteralPath $captureScript)) { throw "找不到初始场景截图脚本：$captureScript" }
    $arguments += ' -ExecCmds="py ' + $captureScript + '"'
}
Start-Process -FilePath $ueEditor -ArgumentList $arguments -WorkingDirectory $projectCache -WindowStyle Hidden -PassThru | Select-Object Id,ProcessName
