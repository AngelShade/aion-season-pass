param([Parameter(Mandatory=$true)][string]$OutputRoot)
$ErrorActionPreference='Stop'
$output=[IO.Path]::GetFullPath($OutputRoot)
$source=[IO.Path]::GetFullPath($PSScriptRoot)
if($output.StartsWith($source+'\',[StringComparison]::OrdinalIgnoreCase) -or $output -eq $source){throw 'Choose a build directory outside the source checkout.'}
New-Item -ItemType Directory -Force -Path $output | Out-Null
Push-Location $source
try {
 & mvn '-pl' 'game-server' '-am' "-Daion.build.root=$output" 'package'
 if($LASTEXITCODE -ne 0){throw 'Server build failed.'}
} finally {Pop-Location}
$archive=Join-Path $output 'game-server/game-server.zip'
if(-not (Test-Path -LiteralPath $archive)){throw 'Server distribution was not produced.'}
$hash=(Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
Set-Content -LiteralPath ($archive+'.sha256') -Encoding ascii -Value ($hash+'  '+[IO.Path]::GetFileName($archive))
$integration=@{
 version=1
 archiveSha256=$hash
 sourceManifestSha256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $source 'tools/modules/source-baseline.json')).Hash.ToLowerInvariant()
}
$integration | ConvertTo-Json | Set-Content -LiteralPath ($archive+'.modules.json') -Encoding ascii
Write-Output "OK: complete server distribution built: $archive"
