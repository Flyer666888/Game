param(
    [switch]$VR
)

$ueEditor = 'D:\浏览器下载\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe'
$uproject = Join-Path $PSScriptRoot 'experiment.uproject'

if (-not (Test-Path -LiteralPath $ueEditor)) {
    throw "找不到 UE 5.8 编辑器：$ueEditor"
}
if (-not (Test-Path -LiteralPath $uproject)) {
    throw "找不到项目文件：$uproject"
}

$arguments = '"' + $uproject + '" -game -windowed -ResX=1600 -ResY=900 -DDC-ForceMemoryCache'
if ($VR) {
    $arguments += ' -vr'
} else {
    $arguments += ' -nohmd'
}

Start-Process -FilePath $ueEditor -ArgumentList $arguments -WorkingDirectory $PSScriptRoot
