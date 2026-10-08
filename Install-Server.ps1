param([Parameter(Mandatory=$true)][string]$Archive,[Parameter(Mandatory=$true)][string]$Destination)
$ErrorActionPreference='Stop'
$archivePath=(Resolve-Path -LiteralPath $Archive).Path
$target=[IO.Path]::GetFullPath($Destination).TrimEnd('\')
if([IO.Path]::GetPathRoot($target).TrimEnd('\') -eq $target){throw 'Use a dedicated server folder.'}
if(Test-Path -LiteralPath $target){throw 'Use a new destination; existing server files are preserved.'}
$checksum=Get-Content -Raw -LiteralPath ($archivePath+'.sha256')
if($checksum -notmatch '^([0-9a-fA-F]{64})\s'){throw 'Invalid distribution checksum.'}
if((Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash -ne $Matches[1]){throw 'Distribution checksum mismatch.'}
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip=[IO.Compression.ZipFile]::OpenRead($archivePath)
try {
 $jars=@($zip.Entries | Where-Object FullName -Match '(^|/)libs/game-server-4\.8-SNAPSHOT\.jar$')
 if($jars.Count -ne 1){throw 'Invalid server distribution.'}
 $prefix=$jars[0].FullName.Substring(0,$jars[0].FullName.Length-'libs/game-server-4.8-SNAPSHOT.jar'.Length)
 foreach($entry in $zip.Entries){
  if(-not $entry.FullName.StartsWith($prefix)){throw 'Mixed distribution roots.'}
  $relative=$entry.FullName.Substring($prefix.Length)
  $path=[IO.Path]::GetFullPath((Join-Path $target $relative))
  if($relative -and -not $path.StartsWith($target+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid distribution path.'}
 }
 foreach($required in @('config/season-pass/season.properties','config/season-pass/schema.sql','config/season-pass/missions.tsv','config/season-pass/rewards.tsv','config/season-pass/media/pass.html','data/static_data/items/item_templates.xml','sql/aion_gs.sql')){
  if(-not $zip.GetEntry($prefix+$required)){throw "Missing distribution dependency: $required"}
 }
 New-Item -ItemType Directory -Path $target | Out-Null
 foreach($entry in $zip.Entries){
  $relative=$entry.FullName.Substring($prefix.Length)
  if(-not $relative -or $entry.FullName.EndsWith('/')){continue}
  $path=Join-Path $target $relative
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
  [IO.Compression.ZipFileExtensions]::ExtractToFile($entry,$path,$false)
 }
} finally {$zip.Dispose()}
Write-Output "OK: server distribution installed in $target. Configure database and login-server settings before starting it."
