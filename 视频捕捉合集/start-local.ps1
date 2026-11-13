$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$port = 8000
while ($port -le 8020) {
    $probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $port)
    try { $probe.Start(); $probe.Stop(); break } catch { $port++ }
}
if ($port -gt 8020) { throw 'No free port available (8000-8020).' }
$server = Start-Process -FilePath "$PSScriptRoot\runtime\node.exe" -ArgumentList @('server.js', "$port") -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput "$PSScriptRoot\server-$port.log" -RedirectStandardError "$PSScriptRoot\server-$port.error.log" -PassThru
$ready = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    try { $response = Invoke-WebRequest "http://localhost:$port/" -UseBasicParsing; if ($response.StatusCode -eq 200) { $ready = $true; break } } catch { Start-Sleep -Milliseconds 200 }
}
if (-not $ready) { throw 'Server failed to start. Check server error log.' }
@{ ProcessId = $server.Id; Port = $port; URL = "http://localhost:$port/" } | ConvertTo-Json | Set-Content -LiteralPath "$PSScriptRoot\running.json" -Encoding UTF8
try { Start-Process "http://localhost:$port/" } catch { Write-Host "Open this address in Edge or Chrome: http://localhost:$port/" }
Write-Host "Started: http://localhost:$port/"
