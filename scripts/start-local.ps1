$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path (Split-Path $Root) 'venv/Scripts/python.exe'
$Logs = Join-Path (Split-Path $Root) 'runtime'
if (Get-NetTCPConnection -LocalPort 8876 -State Listen -ErrorAction SilentlyContinue) {
  throw 'Port 8876 already has a listener. Inspect its identity; do not start a second coordinator.'
}
if (-not (Test-Path (Join-Path $Root 'private/roles.json'))) { throw 'Registry not provisioned' }
New-Item -ItemType Directory -Path $Logs -Force | Out-Null
$stamp = Get-Date -Format yyyyMMdd-HHmmss
$process = Start-Process $Python -ArgumentList @(('"'+(Join-Path $Root 'server.py')+'"'),'--port','8876') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs "$stamp.stdout.log") -RedirectStandardError (Join-Path $Logs "$stamp.stderr.log") -PassThru
for ($attempt=0; $attempt -lt 50; $attempt++) {
  if ($process.HasExited) { throw "Coordinator exited; inspect $Logs" }
  try {
    $health = Invoke-RestMethod 'http://127.0.0.1:8876/health' -TimeoutSec 1
    if ($health.status -eq 'UP') { Write-Host "Coordinator UP; launcher PID $($process.Id); loopback port 8876"; return }
  } catch { }
  Start-Sleep -Milliseconds 100
}
throw "Coordinator did not become ready; inspect $Logs and process $($process.Id)"
