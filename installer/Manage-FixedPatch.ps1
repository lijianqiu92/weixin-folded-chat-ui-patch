param([ValidateSet('Install','Restore')][string]$Mode='Install', [switch]$CheckOnly, [switch]$CheckHostOnly)
$ErrorActionPreference='Stop'
$folder=$PSScriptRoot
$target='C:\Program Files\Tencent\Weixin\4.2.0.13\Weixin.dll'
$originalHash='afe3d02c58bada3c35009c0cd58ee1f57b2a00fe53237d0dce649107fddb9a20'
$patchedHash='095b058a672774b1107595dfcdc1c1e3b3879b8363429d1564d5b975dbca2f24'
function Hash([string]$path) {
 $stream=[System.IO.File]::OpenRead($path)
 $sha=[System.Security.Cryptography.SHA256]::Create()
 try { return [System.BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
 finally { $sha.Dispose(); $stream.Dispose() }
}
try {
 # CMD may inherit a PowerShell 7 PSModulePath; explicitly load Windows PowerShell's own modules.
 Import-Module ($PSHOME+'\Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -ErrorAction Stop
 Import-Module ($PSHOME+'\Modules\Microsoft.PowerShell.Management\Microsoft.PowerShell.Management.psd1') -ErrorAction Stop
 if ($CheckHostOnly) { Write-Host 'HOST CHECK PASSED. No files or processes were modified.'; exit 0 }
 if ($CheckOnly) {
  Write-Host ('PowerShell '+$PSVersionTable.PSVersion.ToString())
  if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw 'Weixin.dll not found.' }
  Write-Host ('Installed DLL SHA256: '+(Hash $target))
  $checkSource=Join-Path $folder 'Weixin.UI-patched.dll'
  $checkBackup=Join-Path $folder 'Weixin.original.dll'
  if ((Hash $checkSource) -ne $patchedHash) { throw 'Patch file hash mismatch.' }
  if ((Hash $checkBackup) -ne $originalHash) { throw 'Original backup hash mismatch.' }
  Write-Host 'READ-ONLY CHECK PASSED. No program or process was modified.'
  exit 0
 }
 try { Start-Transcript -LiteralPath (Join-Path $folder 'installer-last-run.log') -Force | Out-Null } catch {}
 $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
 $principal=New-Object Security.Principal.WindowsPrincipal($identity)
 if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  $argsList=@('-NoProfile','-File',('"'+$PSCommandPath+'"'),'-Mode',$Mode)
  Start-Process -FilePath 'powershell.exe' -ArgumentList $argsList -Verb RunAs -Wait
  exit
 }
 if (-not (Test-Path -LiteralPath $target -PathType Leaf)) { throw 'This exact Weixin installation was not found.' }
 $currentHash=Hash $target
 $desiredHash=if ($Mode -eq 'Install') {$patchedHash} else {$originalHash}
 if ($currentHash -eq $desiredHash) { Write-Host 'Already in the requested state.'; Read-Host 'Press Enter to close'; exit }
 $requiredHash=if ($Mode -eq 'Install') {$originalHash} else {$patchedHash}
 if ($currentHash -ne $requiredHash) { throw 'Weixin.dll has changed or Weixin was updated. No changes made.' }
 $source=Join-Path $folder $(if ($Mode -eq 'Install') {'Weixin.UI-patched.dll'} else {'Weixin.original.dll'})
 $backup=Join-Path $folder 'Weixin.original.dll'
 if ((Hash $source) -ne $desiredHash -or (Hash $backup) -ne $originalHash) { throw 'Patch or original backup verification failed. No changes made.' }
 Write-Host 'Please fully exit Weixin (including its tray icon) before continuing.'
 while (Get-Process -Name Weixin -ErrorAction SilentlyContinue) {
  Read-Host 'Weixin is still running. Exit it, then press Enter to check again'
 }
 # Recheck after the wait; a background updater may have changed this file.
 if ((Hash $target) -ne $requiredHash) { throw 'The program changed while waiting. No changes made.' }
 $stage=Join-Path (Split-Path -LiteralPath $target) 'Weixin.dll.ui-patch-staged'
 Copy-Item -LiteralPath $source -Destination $stage -Force
 if ((Hash $stage) -ne $desiredHash) { throw 'Staged file verification failed.' }
 # Replacement is on the same volume. The independently verified original is preserved in this folder.
 [System.IO.File]::Replace($stage,$target,$null)
 if ((Hash $target) -ne $desiredHash) { throw 'Installed file verification failed. Use Restore-Original.cmd.' }
 Write-Host ($Mode+' completed. You can now reopen Weixin.')
 Write-Host 'No startup task, service, registry entry, account data, or chat database was changed.'
 Read-Host 'Press Enter to close'
} catch {
 Write-Host ('ERROR: '+$_.Exception.Message) -ForegroundColor Red
 if ($CheckOnly -or $CheckHostOnly) { exit 1 }
 Read-Host 'Press Enter to close'
 exit 1
}
