param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$projectDirectory = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$receiptFile = Join-Path $projectDirectory 'Docs\Gameplay\OpenXRRecovery1108\MetaServiceRestart.json'
$service = Get-Service -Name OVRService -ErrorAction Stop
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdministrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($CheckOnly) {
    [pscustomobject]@{
        Status = 'Ready'
        Service = $service.Name
        ServiceStatus = [string]$service.Status
        IsAdministrator = $isAdministrator
        Action = 'Restart OVRService only; no registry, driver, project or save changes.'
        ApplicationsStarted = $false
    } | ConvertTo-Json
    exit 0
}
if (-not $isAdministrator) { throw 'Restarting OVRService requires Windows administrator consent.' }
try {
    Restart-Service -Name OVRService -ErrorAction Stop
    $service = Get-Service -Name OVRService
    $service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Running, [TimeSpan]::FromSeconds(30))
    [pscustomobject]@{
        Status = 'Passed'
        Service = 'OVRService'
        CompletedAt = [DateTimeOffset]::Now.ToString('o')
        RegistryChanged = $false
        ProjectChanged = $false
    } | ConvertTo-Json | Set-Content -LiteralPath $receiptFile -Encoding UTF8
} catch {
    [pscustomobject]@{
        Status = 'Failed'
        CompletedAt = [DateTimeOffset]::Now.ToString('o')
        Error = $_.Exception.Message
    } | ConvertTo-Json | Set-Content -LiteralPath $receiptFile -Encoding UTF8
    exit 1
}
exit 0
