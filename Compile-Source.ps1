param([string]$EditorData = 'D:\BaiduNetdiskDownload\2022.3.48f1c1\Editor\Data')
$ErrorActionPreference='Stop'
$taskRoot=$PSScriptRoot
$project=Join-Path $taskRoot 'InklineRooftops'
$evidence=Join-Path $taskRoot 'Evidence'
New-Item -ItemType Directory -Path $evidence -Force | Out-Null
$runtimeOut=Join-Path $evidence 'Inkline.Runtime.dll'
$editorOut=Join-Path $evidence 'Inkline.Editor.dll'
$refs=@(Get-ChildItem -LiteralPath (Join-Path $EditorData 'NetStandard\ref\2.1.0') -Filter '*.dll')
$refs+=@(Get-ChildItem -LiteralPath (Join-Path $EditorData 'Managed\UnityEngine') -Filter '*.dll')
$common=@('-nologo','-target:library','-nostdlib+','-langversion:9.0','-define:UNITY_2022_3,UNITY_EDITOR,UNITY_STANDALONE_WIN')
$common+=@($refs | ForEach-Object { '-r:"'+$_.FullName+'"' })
$runtimeArgs=$common+@('-out:"'+$runtimeOut+'"')+@(Get-ChildItem -LiteralPath (Join-Path $project 'Assets\Inkline\Runtime') -Filter '*.cs' | ForEach-Object {'"'+$_.FullName+'"'})
$rsp=Join-Path $evidence 'runtime-compile.rsp'
$runtimeArgs | Set-Content -LiteralPath $rsp -Encoding utf8
$dotnet=Join-Path $EditorData 'NetCoreRuntime\dotnet.exe'
$compiler=Join-Path $EditorData 'DotNetSdkRoslyn\csc.dll'
& $dotnet $compiler ('@'+$rsp) 2>&1 | Tee-Object -FilePath (Join-Path $evidence 'runtime-compile.log')
if($LASTEXITCODE -ne 0) { throw 'Runtime source compilation failed' }
$editorArgs=$common+@('-r:"'+$runtimeOut+'"','-out:"'+$editorOut+'"')+@(Get-ChildItem -LiteralPath (Join-Path $project 'Assets\Inkline\Editor') -Filter '*.cs' | ForEach-Object {'"'+$_.FullName+'"'})
$rsp=Join-Path $evidence 'editor-compile.rsp'
$editorArgs | Set-Content -LiteralPath $rsp -Encoding utf8
& $dotnet $compiler ('@'+$rsp) 2>&1 | Tee-Object -FilePath (Join-Path $evidence 'editor-compile.log')
if($LASTEXITCODE -ne 0) { throw 'Editor source compilation failed' }
"PASS: C# runtime and editor sources compiled against installed Unity assemblies. This is NOT a Unity import, shader compile, Play Mode or build test." | Tee-Object -FilePath (Join-Path $evidence 'source-compile-result.txt')
