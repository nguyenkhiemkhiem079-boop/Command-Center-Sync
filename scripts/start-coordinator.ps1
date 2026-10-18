$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
if (-not (Test-Path '.\private\roles.json')) {
  Write-Host 'First run: py -3 bootstrap.py' -ForegroundColor Yellow
  exit 1
}
& py -3 server.py --port 8876
