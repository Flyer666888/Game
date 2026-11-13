param(
    [ValidateSet('Editor', 'Game')]
    [string]$Target = 'Editor'
)

$ErrorActionPreference = 'Stop'
$buildRoot = 'C:\Users\21475\.codex\visualizations\2026\10\01\01a0f77b-1abb-70a0-9543-7d60afd089de'
$engineRoot = 'D:\浏览器下载\UE_5.8'
$projectRoot = $PSScriptRoot

function Ensure-DirectoryJunction([string]$AliasPath, [string]$TargetPath) {
    if (-not (Test-Path -LiteralPath $TargetPath -PathType Container)) {
        throw "Directory does not exist: $TargetPath"
    }
    if (Test-Path -LiteralPath $AliasPath) {
        $alias = Get-Item -LiteralPath $AliasPath -Force
        $expectedTarget = [IO.Path]::GetFullPath($TargetPath).TrimEnd('\')
        $actualTarget = [string]$alias.Target
        if ($alias.LinkType -ne 'Junction' -or
            $actualTarget.TrimEnd('\') -ine $expectedTarget) {
            throw "Existing build alias points to a different directory: $AliasPath"
        }
    } else {
        New-Item -ItemType Junction -Path $AliasPath -Target $TargetPath | Out-Null
    }
}

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
$engineAlias = Join-Path $buildRoot 'UE58'
$projectAlias = Join-Path $buildRoot 'CombatProject'
Ensure-DirectoryJunction $engineAlias $engineRoot
Ensure-DirectoryJunction $projectAlias $projectRoot

$buildTool = Join-Path $engineAlias 'Engine\Build\BatchFiles\Build.bat'
$projectFile = Join-Path $projectAlias 'experiment.uproject'
$targetName = if ($Target -eq 'Editor') { 'experimentEditor' } else { 'experiment' }
$logFile = Join-Path $projectAlias "Docs\AI\BuildLog-CombatModule-$Target-latest.txt"
& $buildTool $targetName Win64 Development "-Project=$projectFile" `
    -NoHotReloadFromIDE -NoUBA -MaxParallelActions=4 -WaitMutex "-Log=$logFile"
$buildExitCode = $LASTEXITCODE
Write-Host "Build exit code: $buildExitCode"
Write-Host "Build log: $logFile"
exit $buildExitCode
