param([Parameter(Mandatory=$true)][string]$PreparedPath)
$ErrorActionPreference='Stop'
$prepared=(Resolve-Path -LiteralPath $PreparedPath).Path
$manifest=Get-Content -Raw -LiteralPath (Join-Path $prepared 'manifest.json') | ConvertFrom-Json
if($manifest.feature -ne 'daeva-season-pass'){throw 'Wrong patch type.'}
$client=(Resolve-Path -LiteralPath $manifest.clientRoot).Path
foreach($process in @(Get-Process -Name 'aion.bin','aion' -ErrorAction SilentlyContinue)){
 if(-not $process.Path){throw 'Cannot verify running Aion path.'}
 if($process.Path.StartsWith($client+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Close Aion normally before installing Season Pass.'}
}
if((Get-FileHash -LiteralPath (Join-Path $client 'Pub.key')).Hash -ne $manifest.sourceKey){throw 'Stock model key changed.'}
$paths=@{}
foreach($e in $manifest.files){
 if($e.path -match '(^/|^[A-Za-z]:|(^|/)\.\.(/|$))' -or $paths.ContainsKey($e.path)){throw 'Invalid replacement path.'}
 $paths[$e.path]=$true
 $target=[IO.Path]::GetFullPath((Join-Path $client $e.path))
 if(-not $target.StartsWith($client+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Replacement outside client.'}
 if($e.path -notmatch '^(bin64/((Game|AionMarketShortcut|crysystem|AionIconBridge)\.dll|AionIconBridge\.index)|Addon\.key|bin32/bin32\.pak\.sig|Data/func_pet/func_pet\.pak\.sig|Plugin/RelicCalc/RelicCalc\.pak(\.sig)?|Data/ui/ui\.pak|Textures/ui/ui\.pak|L10N/enu/Data/data\.pak|Data/ui/game_hud_s[12]/game_hud_s[12]\.pak|DXVK/(installed\.json|graphics-menu/(installed\.json|package/(manifest\.json|bin64/Game\.dll|L10N/enu/Data/data\.pak)))|DXVK-backups/service-menu-graphics-\d{8}-\d{6}-\d{6}/((cursor-base/)?bin64/Game\.dll|L10N/enu/Data/data\.pak)|(MarketShortcut|SpeechBubbles)-backups/\d{8}-\d{6}-\d{3}/manifest\.json)$'){throw "Unexpected replacement: $($e.path)"}
 if((Get-FileHash -LiteralPath (Join-Path $prepared $e.path)).Hash -ne $e.installed){throw 'Prepared file changed.'}
 if($null -eq $e.original){if(Test-Path -LiteralPath $target){throw 'Added file already exists.'}}
 elseif((Get-FileHash -LiteralPath $target).Hash -ne $e.original){throw "Client changed: $($e.path)"}
}
foreach($e in $manifest.preservedFiles){if((Get-FileHash -LiteralPath (Join-Path $client $e.path)).Hash -ne $e.sha256){throw "Preserved file changed: $($e.path)"}}
$backup=Join-Path $client ('SeasonPass-backups/'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $backup | Out-Null
foreach($e in $manifest.files){
 if($null -eq $e.original){continue}
 $saved=Join-Path $backup $e.path
 New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
 Copy-Item -LiteralPath (Join-Path $client $e.path) -Destination $saved
 if((Get-FileHash -LiteralPath $saved).Hash -ne $e.original){throw 'Backup verification failed.'}
}
Copy-Item -LiteralPath (Join-Path $prepared 'manifest.json') -Destination (Join-Path $backup 'manifest.json')
try{
 foreach($e in $manifest.files | Sort-Object { $_.path -eq 'bin64/Game.dll' }){
  $target=Join-Path $client $e.path
  New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
  Copy-Item -LiteralPath (Join-Path $prepared $e.path) -Destination $target
  if((Get-FileHash -LiteralPath $target).Hash -ne $e.installed){throw 'Installed verification failed.'}
 }
}catch{
 foreach($e in $manifest.files){
  $target=Join-Path $client $e.path
  if($null -eq $e.original){Remove-Item -LiteralPath $target -ErrorAction SilentlyContinue}
  else{Copy-Item -LiteralPath (Join-Path $backup $e.path) -Destination $target}
 }
 throw
}
Write-Output "OK: Season Pass client installed. Verified recovery backup: $backup"

