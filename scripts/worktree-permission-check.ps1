param([Parameter(Mandatory=$true)][string]$Worktree,[Parameter(Mandatory=$true)][string]$ExpectedOwner)
$ErrorActionPreference='Stop'
if(!(Test-Path -LiteralPath $Worktree -PathType Container)){throw 'Worktree directory missing'}
Write-Host 'Ownership ACL audit only (NO CHANGES):'
Write-Host "Expected owner: $ExpectedOwner"
icacls $Worktree
Write-Warning 'Review the output, create separate Windows accounts/worktrees and configure NTFS deny/write isolation manually.'
Write-Warning 'Registry locks are NOT physical filesystem locks. Do not claim CANT_EDIT OS PASS from this script.'
