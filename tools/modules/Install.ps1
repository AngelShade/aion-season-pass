param(
 [Parameter(Mandatory=$true)][ValidateSet('season-pass','central-market','wardrobe','journey','inventory-warehouse')][string]$Module,
 [Parameter(Mandatory=$true)][ValidateSet('source','server','client')][string]$Kind,
 [Parameter(Mandatory=$true)][string]$Target,
 [Parameter(Mandatory=$true)][string]$OutputRoot,
 [string]$OriginalClient,[string]$ServerUrl='http://127.0.0.1:8091',
 [string]$ServerArchive,[string]$BaselineArchive,[string]$Media
)
$ErrorActionPreference='Stop'
$source=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$output=[IO.Path]::GetFullPath($OutputRoot).TrimEnd('\')
$targetPath=[IO.Path]::GetFullPath($Target).TrimEnd('\')
foreach($excluded in @($source,$targetPath)){
 if($output -eq $excluded -or $output.StartsWith($excluded+'\',[StringComparison]::OrdinalIgnoreCase) -or ($excluded -eq $targetPath -and $excluded.StartsWith($output+'\',[StringComparison]::OrdinalIgnoreCase))){
  throw 'Choose a separate output/recovery folder outside the source and target.'
 }
}
New-Item -ItemType Directory -Force -Path $output | Out-Null
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TEMP=Join-Path $output 'temporary'
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
$manager=Join-Path $PSScriptRoot 'manage.py'
function Run-Python([string[]]$Arguments){
 & python @Arguments
 if($LASTEXITCODE -ne 0){throw 'Module operation failed; inspect the error above.'}
}
if($Kind -eq 'source'){
 Run-Python @($manager,'source','--path',$targetPath,'--module',$Module,'--backups',(Join-Path $output 'archives/server'))
 Write-Output 'Build this cumulative source once, then deploy it with your existing database/configuration. Never replace it with a different standalone fork.'
}elseif($Kind -eq 'server'){
 if(-not $ServerArchive){
  $ServerArchive=Join-Path $output 'build/game-server/game-server.zip'
  $fingerprint=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'source-baseline.json')).Hash
  $cache=Join-Path $output 'build/source-fingerprint.txt'
  if(-not (Test-Path -LiteralPath $ServerArchive) -or -not (Test-Path -LiteralPath ($ServerArchive+'.modules.json')) -or -not (Test-Path -LiteralPath $cache) -or (Get-Content -Raw -LiteralPath $cache).Trim() -ne $fingerprint){
   $buildRoot=Join-Path $output ('build-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
   & (Join-Path $source 'Build-Server.ps1') -OutputRoot $buildRoot
   $ServerArchive=Join-Path $buildRoot 'game-server/game-server.zip'
   # Cache a verified build for subsequent additions, without deleting recovery outputs.
   New-Item -ItemType Directory -Force -Path (Split-Path -Parent (Join-Path $output 'build/game-server/game-server.zip')) | Out-Null
   Copy-Item -LiteralPath $ServerArchive -Destination (Join-Path $output 'build/game-server/game-server.zip')
   Copy-Item -LiteralPath ($ServerArchive+'.sha256') -Destination (Join-Path $output 'build/game-server/game-server.zip.sha256')
   Copy-Item -LiteralPath ($ServerArchive+'.modules.json') -Destination (Join-Path $output 'build/game-server/game-server.zip.modules.json')
   Set-Content -LiteralPath $cache -Value $fingerprint
  }
 }
 $arguments=@($manager,'server','--path',$targetPath,'--module',$Module,'--backups',(Join-Path $output 'archives/server'),'--archive',$ServerArchive)
 if($BaselineArchive){$arguments+=@('--baseline-archive',$BaselineArchive)}
 if($Media){$arguments+=@('--media',$Media)}
 Run-Python $arguments
}else{
 $receipt=Join-Path $targetPath 'Aetherfall-mods.json'
 if(-not $OriginalClient -and (Test-Path -LiteralPath $receipt)){
  $OriginalClient=(Get-Content -Raw -LiteralPath $receipt | ConvertFrom-Json).originalClient
 }
 if(-not $OriginalClient){
  # Keep the original inputs externally so the second module can compose all installed mods.
  $OriginalClient=Join-Path $output ('archives/client/original-'+[guid]::NewGuid().ToString('N'))
  Run-Python @((Join-Path $PSScriptRoot 'snapshot_client.py'),$targetPath,$OriginalClient)
 }
 $prepared=Join-Path $output ('staging/'+$Module+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
 Run-Python @((Join-Path $source 'client-mods/shared-mods/prepare.py'),'--client',$targetPath,'--original-client',$OriginalClient,'--output',$prepared,'--server-url',$ServerUrl,'--mods',$Module)
 Run-Python @((Join-Path $source 'client-mods/shared-mods/verify.py'),$prepared)
 Run-Python @($manager,'check','--path',$targetPath)
 & (Join-Path $source 'client-mods/season-pass/install.ps1') -PreparedPath $prepared -BackupRoot (Join-Path $output 'archives/client')
 Write-Output "Client recovery is printed above. Keep original inputs at $OriginalClient."
 if(Test-Path -LiteralPath ($prepared+'-server-media')){Write-Output "Journey server artwork: $prepared-server-media"}
}
