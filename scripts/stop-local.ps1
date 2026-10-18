$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$listener = @(Get-NetTCPConnection -LocalPort 8876 -State Listen -ErrorAction SilentlyContinue)
if ($listener.Count -eq 0) { Write-Host 'No coordinator listener'; return }
if ($listener.Count -ne 1) { throw 'Ambiguous listener; inspect manually' }
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener[0].OwningProcess)"
$serverPath = (Join-Path $Root 'server.py').Replace('\','/')
$Venv = Join-Path (Split-Path $Root) 'venv'
$pythonHome = ((Get-Content (Join-Path $Venv 'pyvenv.cfg') | Where-Object { $_ -match '^home = ' }) -replace '^home = ','').Trim()
$allowedExecutables = @((Join-Path $Venv 'Scripts/python.exe'),(Join-Path $pythonHome 'python.exe'))
$executableOK = $allowedExecutables | Where-Object { [IO.Path]::GetFullPath($_) -eq $process.ExecutablePath }
$commandPattern = '^"?' + [regex]::Escape($process.ExecutablePath.Replace('\','/')) + '"?\s+"?' + [regex]::Escape($serverPath) + '"?\s+--port\s+8876\s*$'
if (-not $executableOK -or $process.CommandLine.Replace('\','/') -notmatch $commandPattern) {
  throw 'Port belongs to an unrecognized process. Refusing to stop it.'
}
Stop-Process -Id $process.ProcessId
Write-Host 'Coordinator stopped. Active tasks will freeze on restart; worker processes were not stopped.'
