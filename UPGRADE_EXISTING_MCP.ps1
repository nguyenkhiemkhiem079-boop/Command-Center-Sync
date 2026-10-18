param([string]$Target='C:\KTOOL\CommandCenter\MCP')
$ErrorActionPreference='Stop'
$Source=Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceAbs=[IO.Path]::GetFullPath($Source).TrimEnd('\')
$TargetAbs=[IO.Path]::GetFullPath($Target).TrimEnd('\')
if(!(Test-Path -LiteralPath (Join-Path $Target 'server.py'))){throw "Installation not found at $Target. For first installation use 01_SETUP.bat."}
$listener=Get-NetTCPConnection -LocalPort 8876 -State Listen -ErrorAction SilentlyContinue
if($listener){throw 'Coordinator still listens on port 8876. STOP 02_START_DASHBOARD.bat / server.py, then retry.'}
$Backup=Join-Path $Target ('backup-before-v06-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
$PrivateDb=Join-Path $Target 'private\registry.db'
if(Test-Path -LiteralPath $PrivateDb){
  # SQLite online backup includes WAL transaction contents; do NOT use Copy-Item for a live WAL DB.
  py -3 (Join-Path $Source 'backup_registry.py') --db $PrivateDb --out $Backup
  if($LASTEXITCODE -ne 0){throw 'Database backup failed. No files updated.'}
}
if($SourceAbs -eq $TargetAbs){Write-Host 'Already running from target. Backup complete. No copy needed.';exit 0}
$CodeFiles=@('registry.py','server.py','client_mcp.py','qa_runner.py','backup_registry.py','VERSION')
foreach($name in $CodeFiles){
  $src=Join-Path $Source $name
  if(!(Test-Path -LiteralPath $src)){throw "Missing v0.6 source file: $src"}
  $dest=Join-Path $Target $name
  if(Test-Path -LiteralPath $dest){Copy-Item -LiteralPath $dest -Destination (Join-Path $Backup $name) -Force}
  Copy-Item -LiteralPath $src -Destination $dest -Force
}
foreach($folder in @('web','docs')){
  $from=Join-Path $Source $folder;$to=Join-Path $Target $folder
  if(Test-Path -LiteralPath $to){Copy-Item -LiteralPath $to -Destination (Join-Path $Backup $folder) -Recurse -Force}
  New-Item -ItemType Directory -Path $to -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $from '*') -Destination $to -Recurse -Force
}
foreach($name in @('02_START_DASHBOARD.bat','03_TEST_REGISTRY.bat','README_VI.md','README_DASHBOARD_VI.md','START-HERE.txt','START-HERE-DASHBOARD.txt')){
  Copy-Item -LiteralPath (Join-Path $Source $name) -Destination (Join-Path $Target $name) -Force
}
Write-Host 'v0.6 files updated. Existing tokens/private and SQLite database preserved.'
Write-Host "SQLite backup and previous source copy: $Backup"
Write-Warning 'On next startup, any previously ACTIVE ownership locks will become FROZEN (fail closed).'
Write-Host 'Restart coordinator and each MCP stdio client to load new tools.'
