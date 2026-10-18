param([Parameter(Mandatory=$true)][string]$LiteralPath)
$ErrorActionPreference='Stop'
$Item=Get-Item -LiteralPath $LiteralPath -Force
if($Item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Refuse ACL update on reparse path'}
$Acl=Get-Acl -LiteralPath $Item.FullName
$Acl.SetAccessRuleProtection($true,$false)
foreach($Rule in @($Acl.Access)){$null=$Acl.RemoveAccessRuleSpecific($Rule)}
$Current=[Security.Principal.WindowsIdentity]::GetCurrent().User
$System=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
foreach($Sid in @($Current,$System)){
  if($Item.PSIsContainer){
    $Rule=[Security.AccessControl.FileSystemAccessRule]::new($Sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
  }else{$Rule=[Security.AccessControl.FileSystemAccessRule]::new($Sid,'FullControl','Allow')}
  $Acl.AddAccessRule($Rule)
}
Set-Acl -LiteralPath $Item.FullName -AclObject $Acl
$Verified=Get-Acl -LiteralPath $Item.FullName
$Rules=@($Verified.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]))
if(!$Verified.AreAccessRulesProtected -or $Rules.Count -ne 2 -or @($Rules | Where-Object {$_.IdentityReference.Value -notin @($Current.Value,$System.Value) -or $_.AccessControlType -ne 'Allow'}).Count){throw 'Private DACL verification failed'}
Write-Output 'PRIVATE_DACL_VERIFIED'
