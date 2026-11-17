$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$runtimeDir = Join-Path $projectRoot '.local/runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
if (-not (Test-Path (Join-Path $runtimeDir 'evaluation-active.json'))) { '{"active":true}' | Set-Content (Join-Path $runtimeDir 'evaluation-active.json') }
if (-not (Test-Path (Join-Path $runtimeDir 'runtime-settings.json'))) { '{"engine":"evaluation","snapshot_interval_seconds":15,"export_interval_seconds":3}' | Set-Content (Join-Path $runtimeDir 'runtime-settings.json') }
$projectPython = if ($env:COPILOT_PYTHON) { $env:COPILOT_PYTHON } elseif (Test-Path (Join-Path $projectRoot '.venv/Scripts/python.exe')) { Join-Path $projectRoot '.venv/Scripts/python.exe' } elseif (Test-Path (Join-Path $projectRoot '.local/python-path.txt')) { (Get-Content -Raw (Join-Path $projectRoot '.local/python-path.txt')).Trim() } else { (Get-Command python -ErrorAction Stop).Source }
Push-Location -LiteralPath $projectRoot
try {
    & $projectPython scripts/check_lab_startup.py
    if ($LASTEXITCODE -ne 0) { throw 'Lab preflight failed. Start GNS3/VM and configure .local before retrying.' }
    & $projectPython scripts/lab_runtime.py
    if ($LASTEXITCODE -ne 0) { throw 'Lab startup failed.' }
    $servicePids = @{}
    $serviceScripts = @{bridge='live/worker.py';dashboard='copilot/server.py';review='evaluation/service.py'}
    foreach ($serviceName in @('bridge','dashboard','review')) {
        $servicePath = Join-Path $projectRoot $serviceScripts[$serviceName]
        $matchingServiceProcesses = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($servicePath) })
        # Windows venv python.exe is a redirector with a child interpreter.
        # Count logical roots, rather than treating that pair as two servers.
        $matchingProcessIds = @($matchingServiceProcesses | ForEach-Object { $_.ProcessId })
        $matchingServiceProcesses = @($matchingServiceProcesses | Where-Object { $matchingProcessIds -notcontains $_.ParentProcessId })
        if ($matchingServiceProcesses.Count -gt 1) { throw "Multiple $serviceName processes need inspection." }
        if ($matchingServiceProcesses.Count -eq 1) { $servicePids[$serviceName] = $matchingServiceProcesses[0].ProcessId; continue }
        if ($serviceName -in @('dashboard','review')) {
            $servicePort = if ($serviceName -eq 'dashboard') { 8765 } else { 8766 }
            if (Get-NetTCPConnection -State Listen -LocalPort $servicePort -ErrorAction SilentlyContinue) { throw "Port $servicePort is occupied by another application/workspace. Stop that instance first." }
        }
        $child = Start-Process -FilePath $projectPython -ArgumentList @('"' + $servicePath + '"') -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $runtimeDir "$serviceName.log") -RedirectStandardError (Join-Path $runtimeDir "$serviceName-error.log") -PassThru
        $servicePids[$serviceName] = $child.Id
        $servicePids | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot '.local/services.json')
    }
    $servicePids | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot '.local/services.json')
    Write-Output 'Dashboard: http://127.0.0.1:8765'
    Write-Output 'Recorded study: http://127.0.0.1:8766'
    Write-Output 'Automatic AI remains paused by default. Startup does not inject faults.'
} finally { Pop-Location }
