$ErrorActionPreference = 'Stop'
$savedPids = Join-Path $PSScriptRoot '.local/services.json'
if (-not (Test-Path -LiteralPath $savedPids)) { throw 'No saved service IDs. Inspect processes before stopping anything.' }
$servicePids = Get-Content -Raw -LiteralPath $savedPids | ConvertFrom-Json
$serviceScripts = @{bridge='live/worker.py';dashboard='copilot/server.py';review='evaluation/service.py'}
foreach ($serviceName in @('bridge','dashboard','review')) {
    $servicePid = $servicePids.$serviceName
    if (-not $servicePid) { continue }
    $servicePath = Join-Path $PSScriptRoot $serviceScripts[$serviceName]
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $servicePid"
    if ($process -and $process.CommandLine -and $process.CommandLine.Contains($servicePath)) {
        # Include the child interpreter behind a Windows venv redirector.
        & taskkill.exe /PID $servicePid /T /F | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to stop the verified $serviceName process tree." }
        Write-Output "Stopped $serviceName"
    }
}
Write-Output 'GNS3 nodes, database and collector remain running.'
