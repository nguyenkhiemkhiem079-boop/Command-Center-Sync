param([string]$Target='C:\KTOOL\CommandCenter\MCP',[string]$Python='C:\KTOOL\CommandCenter\venv\Scripts\python.exe',[switch]$Apply)
$ErrorActionPreference='Stop'
$Source=(Resolve-Path -LiteralPath $PSScriptRoot).Path
$Target=(Resolve-Path -LiteralPath $Target).Path
if($Source -eq $Target){throw 'Upgrade requires separate reviewed source staging directory'}
if(!(Test-Path -LiteralPath (Join-Path $Target 'private/registry.db'))){throw 'Existing Registry required; no bootstrap or reset permitted'}
$Names=@('registry.py','server.py','client_mcp.py','qa_runner.py','backup_registry.py','ci_scope_gate.py','orchestration.py','trust_vault.py','transaction_sync.py','recovery_manager.py','governance.py','cockpit.py','mission_recovery.py','worktree_manager.py','anti_runtime.py','VERSION','requirements.txt','constraints-windows-py312.txt')
foreach($Folder in @('web','clients','scripts','docs','.github')){
 $Base=Join-Path $Source $Folder
 if(Test-Path -LiteralPath $Base){foreach($File in Get-ChildItem -LiteralPath $Base -File -Recurse){$Names+=($File.FullName.Substring($Source.Length+1))}}
}
foreach($Name in $Names){if(!(Test-Path -LiteralPath (Join-Path $Source $Name) -PathType Leaf)){throw "Missing required upgrade source $Name"}}
if(!$Apply){[pscustomobject]@{mode='DRY_RUN';target=$Target;files=$Names;preserves='private credentials registry and unrelated local files';approval='Run -Apply only for owner-approved candidate while coordinator stopped'} | ConvertTo-Json -Depth 4;exit 0}
if(Get-NetTCPConnection -LocalPort 8876 -State Listen -ErrorAction SilentlyContinue){throw 'Stop verified coordinator before approved upgrade; this script kills no processes'}
if(!(Test-Path -LiteralPath $Python)){throw 'Configured existing venv Python required; no implicit install'}
$Backup=Join-Path (Split-Path -Parent $Target) ('deployments/upgrade-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Backup | Out-Null
& (Join-Path $Source 'scripts/protect-private-path.ps1') -LiteralPath $Backup | Out-Null
& $Python (Join-Path $Source 'backup_registry.py') --db (Join-Path $Target 'private/registry.db') --out $Backup
if($LASTEXITCODE -ne 0){throw 'SQLite backup failed; no source updated'}
$Manifest=@()
foreach($Name in $Names){
 $From=Join-Path $Source $Name;$To=Join-Path $Target $Name;$Old=$null
 if(Test-Path -LiteralPath $To){$Old=(Get-FileHash -LiteralPath $To -Algorithm SHA256).Hash;$Saved=Join-Path $Backup ('source-before/'+$Name);New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Saved) | Out-Null;Copy-Item -LiteralPath $To -Destination $Saved}
 $Manifest += [pscustomobject]@{file=$Name;old_sha256=$Old;new_sha256=(Get-FileHash -LiteralPath $From -Algorithm SHA256).Hash}
}
$Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Backup 'source-manifest.json') -Encoding UTF8
foreach($Name in $Names){$To=Join-Path $Target $Name;New-Item -ItemType Directory -Force -Path (Split-Path -Parent $To) | Out-Null;Copy-Item -LiteralPath (Join-Path $Source $Name) -Destination $To -Force}
Write-Output "Source upgraded with protected backup at $Backup. Existing private data unchanged. Startup performs additive migration after another backup. Restart only owner-approved candidate; validate integrity/RBAC/frozen locks. Rollback uses source-manifest/source-before; never overwrite live DB."
