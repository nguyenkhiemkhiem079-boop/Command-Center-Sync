param(
  [Parameter(Mandatory=$true)][ValidateSet('CODEX','ANTI-01','ANTI-02')][string]$Role,
  [string]$McpConfigPath,
  [switch]$ReplaceExisting
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Adapter = Join-Path $Root 'client_mcp.py'
$Name = 'ktool-' + $Role.ToLowerInvariant()
if ($Role -ne 'CODEX' -and [string]::IsNullOrWhiteSpace($McpConfigPath)) {
  throw 'Workers require the actual MCP JSON config path supplied explicitly with -McpConfigPath. No path is guessed.'
}
if (-not $env:APPDATA) { throw 'APPDATA required' }
$Storage = Join-Path $env:APPDATA ('KTOOLMCP/identities/' + $Role)
$TokenFile = Join-Path $Storage 'client_token.txt'
$Venv = Join-Path (Split-Path $Root) 'venv'
if (-not (Test-Path (Join-Path $Venv 'Scripts/python.exe'))) { $Venv = Join-Path $Root '.client-venv' }
$Python = Join-Path $Venv 'Scripts/python.exe'
$LaunchArgs = @($Adapter,'--identity',$Role,'--token-file',$TokenFile)
$Desired = [pscustomobject]@{ command=$Python; args=$LaunchArgs }
$Cfg = $null
# Inspect conflicts before credential, dependency or client-config mutations.
if ($Role -eq 'CODEX') {
  if (-not (Get-Command codex -ErrorAction SilentlyContinue)) { throw 'Codex CLI required' }
  $existingRaw = & codex mcp get $Name --json 2>$null
  if ($LASTEXITCODE -eq 0) {
    $existing = ($existingRaw -join "`n") | ConvertFrom-Json
    $transport = $existing.transport
    $same = $transport.command -eq $Python -and (($transport.args | ConvertTo-Json -Compress) -eq ($LaunchArgs | ConvertTo-Json -Compress))
    if (-not $same -and -not $ReplaceExisting) { throw "Existing $Name conflicts; review it and explicitly use -ReplaceExisting to approve replacement." }
  } else { $existing = $null; $same = $false }
} else {
  $McpConfigPath = [IO.Path]::GetFullPath($McpConfigPath)
  if (-not (Test-Path -LiteralPath $McpConfigPath -PathType Leaf)) { throw 'Supply an existing actual MCP JSON config file' }
  $Cfg = Get-Content -LiteralPath $McpConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
  if ($null -eq $Cfg.mcpServers) { $Cfg | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) }
  $existing = $Cfg.mcpServers.PSObject.Properties[$Name]
  $same = $existing -and (($existing.Value | ConvertTo-Json -Depth 100 -Compress) -eq ($Desired | ConvertTo-Json -Depth 100 -Compress))
  if ($existing -and -not $same -and -not $ReplaceExisting) { throw "Existing $Name conflicts; review it and explicitly use -ReplaceExisting to approve replacement." }
}
if (-not (Test-Path -LiteralPath $Python)) {
  & py -3 -m venv $Venv
  if ($LASTEXITCODE -ne 0) { throw 'Could not create dedicated client venv' }
}
& $Python -c 'import mcp.server.fastmcp' 2>$null
if ($LASTEXITCODE -ne 0) {
  & $Python -m pip install 'mcp>=1.20,<2'
  if ($LASTEXITCODE -ne 0) { throw 'Dedicated venv dependency installation failed' }
}
New-Item -ItemType Directory -Force -Path $Storage | Out-Null
$Principal = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls $Storage /inheritance:r /grant:r "${Principal}:(OI)(CI)F" 'SYSTEM:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Identity directory ACL failed' }
if (-not (Test-Path -LiteralPath $TokenFile)) {
  $Secret = Read-Host "Paste the $Role registry token (never Google OAuth)" -AsSecureString
  $Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret)
  try {
    $Token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr)
    if ([string]::IsNullOrWhiteSpace($Token)) { throw 'Empty token' }
    [IO.File]::WriteAllText($TokenFile,$Token.Trim(),[Text.UTF8Encoding]::new($false))
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr)
    $Token = $null
  }
}
& icacls $TokenFile /inheritance:r /grant:r "${Principal}:F" 'SYSTEM:F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Credential ACL failed' }
# Separate launcher contains only paths and identity, never credential contents.
$Launcher = Join-Path $Storage ($Name + '.ps1')
$Quote = { param($value) "'" + $value.Replace("'","''") + "'" }
$Line = '& ' + (& $Quote $Python) + ' ' + (($LaunchArgs | ForEach-Object { & $Quote $_ }) -join ' ') + "`nexit `$LASTEXITCODE`n"
[IO.File]::WriteAllText($Launcher,$Line,[Text.UTF8Encoding]::new($false))
if (-not $same) {
  if ($Role -eq 'CODEX') {
    if ($existing) {
      & codex mcp remove $Name
      if ($LASTEXITCODE -ne 0) { throw 'Could not remove approved conflicting entry' }
    }
    & codex mcp add $Name -- $Python @LaunchArgs
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure Codex entry' }
  } else {
    Copy-Item -LiteralPath $McpConfigPath -Destination ($McpConfigPath + '.backup-' + [guid]::NewGuid().ToString('N'))
    $Cfg.mcpServers | Add-Member -NotePropertyName $Name -NotePropertyValue $Desired -Force
    [IO.File]::WriteAllText($McpConfigPath,($Cfg | ConvertTo-Json -Depth 100),[Text.UTF8Encoding]::new($false))
  }
}
Write-Host "Configured $Name with explicit $Role credential reference. Restart/refresh that client's MCP session and verify status. Same-user files are not a security boundary."
