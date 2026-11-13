$ErrorActionPreference='Stop'
$previewRoot=$PSScriptRoot
$template=[IO.File]::ReadAllText((Join-Path $previewRoot 'index.template.html'))
$simulation=[IO.File]::ReadAllText((Join-Path $previewRoot 'simulation.js'))
$view=[IO.File]::ReadAllText((Join-Path $previewRoot 'view.js'))
$html=$template.Replace('/*__SIMULATION__*/',$simulation).Replace('/*__VIEW__*/',$view)
[IO.File]::WriteAllText((Join-Path $previewRoot 'index.html'),$html,[Text.UTF8Encoding]::new($false))
Write-Output 'Self-contained offline index.html created. No external resources required.'
