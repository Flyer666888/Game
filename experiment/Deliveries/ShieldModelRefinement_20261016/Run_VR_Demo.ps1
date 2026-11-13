param([string]$SteamVRManifest)
$ErrorActionPreference = 'Stop'

# SteamVR is selected only for the Unreal child process. This launcher does not
# write OpenXR's global runtime registry setting or the current shell's env.
$taskCache = 'C:\Users\21475\.codex\visualizations\2026\10\01\01a0f77b-1abb-70a0-9543-7d60afd089de'
$projectCache = Join-Path $taskCache 'CombatProject'
$engineCache = Join-Path $taskCache 'UE58'
$enginePhysical = 'D:\浏览器下载\UE_5.8'
$map = '/Game/ReversedScale/Maps/L_CombatLabVR'

function Get-PhysicalDirectory([string]$Directory) {
    $resolved = [IO.Path]::GetFullPath($Directory).TrimEnd('\')
    for ($attempt = 0; $attempt -lt 8; $attempt++) {
        $item = Get-Item -LiteralPath $resolved -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) { return $resolved }
        $target = [string](@($item.Target)[0])
        if (-not $target) { throw "无法解析目录链接：$resolved" }
        if (-not [IO.Path]::IsPathRooted($target)) { $target = Join-Path (Split-Path $resolved -Parent) $target }
        $resolved = [IO.Path]::GetFullPath($target).TrimEnd('\')
    }
    throw "目录链接层级异常：$Directory"
}

function Confirm-ProjectJunction([string]$Link, [string]$Expected) {
    if (Test-Path -LiteralPath $Link) {
        $existing = Get-Item -LiteralPath $Link -Force
        if (($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) {
            throw "ASCII 缓存路径已被普通目录占用：$Link"
        }
        $actual = Get-PhysicalDirectory $Link
        if ($actual -ine (Get-PhysicalDirectory $Expected)) {
            throw "ASCII 缓存链接指向了其他目录：$actual"
        }
    } else {
        New-Item -ItemType Junction -Path $Link -Target $Expected | Out-Null
    }
}

function Find-SteamVRManifest([string]$Requested) {
    if ($Requested) {
        if (-not (Test-Path -LiteralPath $Requested -PathType Leaf)) {
            throw "找不到指定的 SteamVR OpenXR 清单：$Requested"
        }
        return [IO.Path]::GetFullPath($Requested)
    }

    $steamRoots = New-Object 'System.Collections.Generic.List[string]'
    $steamRoots.Add('D:\steam')
    foreach ($registry in @(
        @{ Path = 'HKCU:\Software\Valve\Steam'; Property = 'SteamPath' },
        @{ Path = 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam'; Property = 'InstallPath' },
        @{ Path = 'HKLM:\SOFTWARE\Valve\Steam'; Property = 'InstallPath' }
    )) {
        $entry = Get-ItemProperty -LiteralPath $registry.Path -ErrorAction SilentlyContinue
        if ($entry -and $entry.($registry.Property)) { $steamRoots.Add([string]$entry.($registry.Property)) }
    }
    if (${env:ProgramFiles(x86)}) { $steamRoots.Add((Join-Path ${env:ProgramFiles(x86)} 'Steam')) }

    $libraries = New-Object 'System.Collections.Generic.List[string]'
    foreach ($steamRoot in @($steamRoots | Select-Object -Unique)) {
        $libraries.Add($steamRoot)
        $libraryFile = Join-Path $steamRoot 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $libraryFile -PathType Leaf) {
            foreach ($match in [regex]::Matches([IO.File]::ReadAllText($libraryFile), '"path"\s*"([^"]+)"')) {
                $libraries.Add($match.Groups[1].Value.Replace('\\', '\'))
            }
        }
    }
    foreach ($library in @($libraries | Select-Object -Unique)) {
        $candidate = Join-Path $library 'steamapps\common\SteamVR\steamxr_win64.json'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return [IO.Path]::GetFullPath($candidate) }
    }
    throw '未找到 SteamVR。请先在 Steam 安装 SteamVR，或使用 -SteamVRManifest 指定 steamxr_win64.json。'
}

try {
    $physicalProject = Get-PhysicalDirectory $PSScriptRoot
    $physicalUproject = Join-Path $physicalProject 'experiment.uproject'
    if (-not (Test-Path -LiteralPath $physicalUproject -PathType Leaf)) { throw "找不到项目文件：$physicalUproject" }
    if (-not (Test-Path -LiteralPath $enginePhysical -PathType Container)) { throw "找不到 UE 5.8：$enginePhysical" }
    New-Item -ItemType Directory -Path $taskCache -Force | Out-Null
    Confirm-ProjectJunction $projectCache $physicalProject
    Confirm-ProjectJunction $engineCache $enginePhysical

    $ueEditor = Join-Path $engineCache 'Engine\Binaries\Win64\UnrealEditor.exe'
    $uproject = Join-Path $projectCache 'experiment.uproject'
    $mapFile = Join-Path $projectCache 'Content\ReversedScale\Maps\L_CombatLabVR.umap'
    $inputContext = Join-Path $projectCache 'Content\ReversedScale\Player\VR\Input\IMC_NilinVR.uasset'
    $moduleFile = Join-Path $projectCache 'Binaries\Win64\UnrealEditor-experiment.dll'
    foreach ($required in @($ueEditor, $mapFile, $inputContext, $moduleFile)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "VR Demo 的必需文件缺失：$required" }
    }

    $runtimeManifest = Find-SteamVRManifest $SteamVRManifest
    $manifestData = [IO.File]::ReadAllText($runtimeManifest) | ConvertFrom-Json
    if (-not $manifestData.runtime -or -not $manifestData.runtime.library_path -or
        (($manifestData.runtime.name -notmatch 'SteamVR') -and -not $manifestData.runtime.VALVE_runtime_is_steamvr)) {
        throw "指定的清单不是有效的 SteamVR OpenXR 运行时：$runtimeManifest"
    }
    $steamVRRoot = Split-Path $runtimeManifest -Parent
    $runtimeLibrary = [string]$manifestData.runtime.library_path
    if (-not [IO.Path]::IsPathRooted($runtimeLibrary)) { $runtimeLibrary = Join-Path $steamVRRoot $runtimeLibrary }
    if (-not (Test-Path -LiteralPath $runtimeLibrary -PathType Leaf)) { throw "SteamVR 运行时文件缺失：$runtimeLibrary" }

    $logDirectory = Join-Path $projectCache 'Saved\Logs'
    $shaderWorkingDir = Join-Path $taskCache 'ShaderWorkingDir'
    $ddcPath = Join-Path $taskCache 'DDC'
    foreach ($directory in @($logDirectory, $shaderWorkingDir, $ddcPath)) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }
    $launchStamp = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
    $previewLog = Join-Path $logDirectory ("VRPreview_" + $launchStamp + '.log')
    $launcherLog = Join-Path $logDirectory ("VRLauncher_" + $launchStamp + '.txt')

    # Repeated clicks must not launch a second copy of this VR scene.
    $runningDemos = @(Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine.Contains($map) -and
            ($_.CommandLine.Contains($uproject) -or $_.CommandLine.Contains($physicalUproject)) })
    if ($runningDemos.Count -gt 0) {
        Write-Host ('这个 VR Demo 已在运行，进程 ID：' + (($runningDemos | ForEach-Object ProcessId) -join ', '))
        exit 0
    }

    if (-not (Get-Process -Name vrserver -ErrorAction SilentlyContinue)) {
        $vrStartup = Join-Path $steamVRRoot 'bin\win64\vrstartup.exe'
        if (-not (Test-Path -LiteralPath $vrStartup -PathType Leaf)) { throw "找不到 SteamVR 启动程序：$vrStartup" }
        Write-Host '正在启动 SteamVR，请确认头显及左右手柄已连接。'
        Start-Process -FilePath $vrStartup -WorkingDirectory $steamVRRoot -WindowStyle Hidden | Out-Null
        $startupDeadline = (Get-Date).AddSeconds(30)
        do {
            Start-Sleep -Milliseconds 500
            $server = Get-Process -Name vrserver -ErrorAction SilentlyContinue
        } while (-not $server -and (Get-Date) -lt $startupDeadline)
        if (-not $server) { throw 'SteamVR 在 30 秒内没有启动完成。请手动打开 SteamVR，确认设备正常后再次打开 Demo。' }
        # Give the compositor time to initialize after vrserver appears.
        Start-Sleep -Seconds 2
    }

    $arguments = '"' + $uproject + '" ' + $map + ' -game -vr -windowed -ResX=1280 -ResY=720 -DDC=(InstalledEnginePak,Local) -LocalDataCachePath="' + $ddcPath + '" -NoZenAutoLaunch -ShaderWorkingDir="' + $shaderWorkingDir + '" -abslog="' + $previewLog + '"'
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $ueEditor
    $startInfo.Arguments = $arguments
    $startInfo.WorkingDirectory = $projectCache
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $startInfo.EnvironmentVariables['XR_RUNTIME_JSON'] = $runtimeManifest
    $gameProcess = [System.Diagnostics.Process]::Start($startInfo)
    if (-not $gameProcess) { throw 'UE 进程未能启动。' }

    @(
        'Nilin SteamVR / OpenXR demo launcher',
        ('Local launch time: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')),
        ('Project: ' + $physicalUproject),
        ('Engine: ' + $ueEditor),
        ('Map: ' + $map),
        ('XR_RUNTIME_JSON (child process only): ' + $runtimeManifest),
        ('Unreal process ID: ' + $gameProcess.Id),
        ('Unreal log: ' + $previewLog),
        'Global OpenXR registry and parent process environment were not changed.'
    ) | Set-Content -LiteralPath $launcherLog -Encoding UTF8
    Write-Host ('VR Demo 已启动，进程 ID：' + $gameProcess.Id)
    Write-Host ('SteamVR 运行时：' + $runtimeManifest)
    Write-Host ('运行日志：' + $previewLog)
    Write-Host '请在头显中试玩。若 SteamVR 提示设备未就绪，先确认设备连接状态。'
} catch {
    Write-Host ('VR Demo 启动失败：' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
