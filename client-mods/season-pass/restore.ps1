param([Parameter(Mandatory=$true)][string]$BackupPath)
$ErrorActionPreference='Stop'
$backup=(Resolve-Path -LiteralPath $BackupPath).Path
$m=Get-Content -Raw -LiteralPath (Join-Path $backup 'manifest.json') | ConvertFrom-Json
if($m.feature -ne 'daeva-season-pass'){throw 'Wrong backup type.'}
$client=(Resolve-Path -LiteralPath $m.clientRoot).Path
if(-not $backup.StartsWith($client+'\SeasonPass-backups\',[StringComparison]::OrdinalIgnoreCase)){throw 'Backup must be inside this client.'}
foreach($process in @(Get-Process -Name 'aion.bin','aion' -ErrorAction SilentlyContinue)){
 if(-not $process.Path){throw 'Cannot verify running Aion path.'}
 if($process.Path.StartsWith($client+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Close Aion normally before restoring.'}
}
foreach($e in $m.files){
 $target=[IO.Path]::GetFullPath((Join-Path $client $e.path))
 if(-not $target.StartsWith($client+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid backup path.'}
 if((Get-FileHash -LiteralPath $target).Hash -ne $e.installed){throw "Later client change: $($e.path). Restore that patch first."}
 if($null -ne $e.original -and (Get-FileHash -LiteralPath (Join-Path $backup $e.path)).Hash -ne $e.original){throw 'Backup changed.'}
}
foreach($e in $m.files){
 $target=Join-Path $client $e.path
 if($null -eq $e.original){Remove-Item -LiteralPath $target}
 else{Copy-Item -LiteralPath (Join-Path $backup $e.path) -Destination $target}
}
Write-Output 'OK: client season-pass patch restored. Server season data and rewards are retained.'
