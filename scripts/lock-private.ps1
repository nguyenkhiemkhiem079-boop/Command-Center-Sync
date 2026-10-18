$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Private = Join-Path $Root 'private'
if (-not (Test-Path $Private)) { throw 'Run py -3 bootstrap.py first' }
$Principal = "$env:USERDOMAIN\$env:USERNAME"
& icacls $Private /inheritance:r /grant:r "${Principal}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'ACL failed; do not start coordinator until private/ is protected' }
Write-Host "Restricted private/ to $Principal and SYSTEM" -ForegroundColor Green
