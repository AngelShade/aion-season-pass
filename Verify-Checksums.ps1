$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath $PSScriptRoot).Path
foreach($line in Get-Content -LiteralPath (Join-Path $root 'CHECKSUMS.sha256')){
    if($line -notmatch '^([0-9a-f]{64})  (.+)$'){throw "Invalid checksum row: $line"}
    $relative=$Matches[2].Replace('/','\')
    $target=[IO.Path]::GetFullPath((Join-Path $root $relative))
    if(-not $target.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw "Invalid package path: $relative"}
    if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Matches[1]){throw "Checksum mismatch: $relative"}
}
Write-Output 'OK: all repository package checksums match.'
