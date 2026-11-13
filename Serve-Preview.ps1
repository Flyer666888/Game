param([int]$Port=8765)
$ErrorActionPreference='Stop'
$serveRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'BrowserPreview'))
$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$Port)
$listener.Start()
Write-Output "INKLINE preview: http://127.0.0.1:$Port/ (loopback only; Ctrl+C stops)"
try {
  while($true) {
    $client=$listener.AcceptTcpClient()
    try {
      $stream=$client.GetStream(); $stream.ReadTimeout=3000
      $reader=[IO.StreamReader]::new($stream,[Text.Encoding]::ASCII,$false,1024,$true)
      $request=$reader.ReadLine()
      if(!$request){continue}
      while($reader.ReadLine() -ne ''){}
      $url=($request -split ' ')[1].Split('?')[0]
      if($url -eq '/'){$url='/index.html'}
      $relative=[Uri]::UnescapeDataString($url).TrimStart('/').Replace('/',[IO.Path]::DirectorySeparatorChar)
      $target=[IO.Path]::GetFullPath((Join-Path $serveRoot $relative))
      if(!$target.StartsWith($serveRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or !(Test-Path -LiteralPath $target -PathType Leaf)) {
        $bytes=[Text.Encoding]::UTF8.GetBytes('Not found');$status='404 Not Found';$mime='text/plain'
      } else {
        $bytes=[IO.File]::ReadAllBytes($target);$status='200 OK'
        $mime=switch([IO.Path]::GetExtension($target)){'.html'{'text/html; charset=utf-8'} '.js'{'text/javascript; charset=utf-8'} '.css'{'text/css; charset=utf-8'} default{'application/octet-stream'}}
      }
      $header=[Text.Encoding]::ASCII.GetBytes("HTTP/1.1 $status`r`nContent-Type: $mime`r`nContent-Length: $($bytes.Length)`r`nCache-Control: no-store`r`nConnection: close`r`n`r`n")
      $stream.Write($header,0,$header.Length);$stream.Write($bytes,0,$bytes.Length);$stream.Flush()
    } catch {Write-Output $_.Exception.Message} finally {$client.Dispose()}
  }
} finally {$listener.Stop()}
