Write-Host 'Checking local registry health...' -ForegroundColor Cyan
try {
  $Status = Invoke-RestMethod -Uri 'http://127.0.0.1:8876/health' -TimeoutSec 5
  Write-Host "HTTP coordinator is $($Status.status)" -ForegroundColor Green
} catch { Write-Error 'Cannot connect to server. Run scripts/start-coordinator.ps1'; exit 1 }
Write-Host 'This is NOT the MCP tool check. In Codex/Antigravity, ask to invoke ktool-control status.'
