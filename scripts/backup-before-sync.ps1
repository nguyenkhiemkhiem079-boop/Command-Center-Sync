$ErrorActionPreference='Stop'
$Root=Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
py -3 (Join-Path $Root 'backup_registry.py') --db (Join-Path $Root 'private\registry.db') --out (Join-Path $Root 'private\backups')
if($LASTEXITCODE -ne 0){throw 'Backup failed; do not sync.'}
Write-Host 'Registry backup done. Check SHA256 and QA gate before Git integration.'
