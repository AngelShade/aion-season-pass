param([Parameter(Mandatory=$true)][string]$BackupPath)
$ErrorActionPreference='Stop'
$backup=(Resolve-Path -LiteralPath $BackupPath).Path
$m=Get-Content -Raw -LiteralPath (Join-Path $backup 'manifest.json') | ConvertFrom-Json
if($m.feature -ne 'daeva-season-pass'){throw 'Wrong backup type.'}
$client=(Resolve-Path -LiteralPath $m.clientRoot).Path
if(-not $backup.StartsWith($client+'\SeasonPass-backups\',[StringComparison]::OrdinalIgnoreCase)){
 if(-not $m.recoveryPath -or [IO.Path]::GetFullPath($m.recoveryPath) -ne $backup -or $backup.StartsWith($client+'\',[StringComparison]::OrdinalIgnoreCase)){
  throw 'External backup location does not match its installer recovery record.'
 }
}
foreach($process in @(Get-Process -Name 'aion.bin','aion' -ErrorAction SilentlyContinue)){
 if(-not $process.Path){throw 'Cannot verify running Aion path.'}
 if($process.Path.StartsWith($client+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Close Aion normally before restoring.'}
}
$paths=@{}
foreach($e in $m.files){
 if($e.path -match '(^/|^[A-Za-z]:|(^|/)\.\.(/|$))' -or $paths.ContainsKey($e.path)){throw 'Invalid recovery path.'}
 $paths[$e.path]=$true
 $target=[IO.Path]::GetFullPath((Join-Path $client $e.path))
 if(-not $target.StartsWith($client+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid backup path.'}
 if((Get-FileHash -LiteralPath $target).Hash -ne $e.installed){throw "Later client change: $($e.path). Restore that patch first."}
 if($null -ne $e.original -and (Get-FileHash -LiteralPath (Join-Path $backup $e.path)).Hash -ne $e.original){throw 'Backup changed.'}
}
$current=@{}
foreach($e in $m.files){$current[$e.path]=[IO.File]::ReadAllBytes((Join-Path $client $e.path))}
try{
 foreach($e in $m.files){
  $target=Join-Path $client $e.path
  if($null -eq $e.original){Remove-Item -LiteralPath $target}
  else{
   Copy-Item -LiteralPath (Join-Path $backup $e.path) -Destination $target
   if((Get-FileHash -LiteralPath $target).Hash -ne $e.original){throw 'Restoration verification failed.'}
  }
 }
}catch{
 foreach($e in $m.files){[IO.File]::WriteAllBytes((Join-Path $client $e.path),$current[$e.path])}
 throw
}
Write-Output 'OK: client season-pass patch restored. Server season data and rewards are retained.'
