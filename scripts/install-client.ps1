param(
  [Parameter(Mandatory=$true)][ValidateSet('CODEX','ANTI-01','ANTI-02')][string]$Role
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Adapter = (Join-Path $Root 'client_mcp.py')
Write-Host "K-TOOL Client installer: $Role in Windows user $env:USERNAME" -ForegroundColor Cyan
Write-Host 'Run this script only inside the Windows profile dedicated to this role.' -ForegroundColor Yellow
& py -3 --version
if ($LASTEXITCODE -ne 0) { throw 'Python launcher not found: install Python 3.11+ and check Add to PATH' }
& py -3 -m pip install --user 'mcp>=1.20,<2'
if ($LASTEXITCODE -ne 0) { throw 'Python MCP SDK install failed' }
$Storage = Join-Path $env:APPDATA 'KTOOLMCP'
New-Item -ItemType Directory -Force -Path $Storage | Out-Null
$Secret = Read-Host "Paste the $Role ONE-TIME token" -AsSecureString
$Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
try {
  $Token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr)
  if ([string]::IsNullOrWhiteSpace($Token)) { throw 'Empty token' }
  $TokenFile = Join-Path $Storage 'client_token.txt'
  [IO.File]::WriteAllText($TokenFile, $Token.Trim(), ([System.Text.UTF8Encoding]::new($false)))
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr)
  $Token = $null
}
# Remove inherited broad access; grant current user + SYSTEM. Run on local NTFS.
& icacls $Storage /inheritance:r /grant:r "${env:USERNAME}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' | Out-Null
& icacls $TokenFile /inheritance:r /grant:r "${env:USERNAME}:R" 'SYSTEM:F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Failed setting token file ACL' }
Write-Host 'Role token installed in per-Windows-user APPDATA (do not commit or share).' -ForegroundColor Green
if ($Role -eq 'CODEX') {
  $codex = Get-Command codex -ErrorAction SilentlyContinue
  if (-not $codex) {
    Write-Warning 'Codex CLI not found. Install/open Codex CLI then run: codex mcp add ktool-control -- py -3 "<ABSOLUTE_PATH_TO_client_mcp.py>"'
  } else {
    & codex mcp add ktool-control -- py -3 $Adapter
    if ($LASTEXITCODE -ne 0) { throw 'codex mcp add failed (maybe already installed; inspect codex mcp list)' }
    & codex mcp list
  }
} else {
  $ConfigDir = Join-Path $env:USERPROFILE '.gemini\config'
  New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
  $ConfigPath = Join-Path $ConfigDir 'mcp_config.json'
  if (Test-Path $ConfigPath) {
    Copy-Item $ConfigPath ($ConfigPath+'.backup-'+(Get-Date -Format yyyyMMddHHmmss))
    $Raw = Get-Content -Path $ConfigPath -Raw -Encoding UTF8
    $Cfg = ConvertFrom-Json -InputObject $Raw
  } else { $Cfg = [pscustomobject]@{} }
  if ($null -eq $Cfg.mcpServers) { $Cfg | Add-Member -NotePropertyName 'mcpServers' -NotePropertyValue ([pscustomobject]@{}) -Force }
  $Cfg.mcpServers | Add-Member -NotePropertyName 'ktool-control' -NotePropertyValue ([pscustomobject]@{ command='py'; args=@('-3',$Adapter) }) -Force
  $Json = ConvertTo-Json $Cfg -Depth 15
  [IO.File]::WriteAllText($ConfigPath, $Json, ([System.Text.UTF8Encoding]::new($false)))
  Write-Host "Updated $ConfigPath" -ForegroundColor Green
  Write-Host 'Antigravity IDE: ... > MCP Servers > Manage MCP Servers > Refresh.'
  Write-Host 'If raw-config UI uses a different path, merge the ktool-control entry into that exact file.' -ForegroundColor Yellow
}
Write-Host 'Open a new client session and ask the agent to call the ktool-control status tool.' -ForegroundColor Cyan
