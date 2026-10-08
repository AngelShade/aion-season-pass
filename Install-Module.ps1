param(
 [Parameter(Mandatory=$true)][ValidateSet('source','server','client')][string]$Kind,
 [Parameter(Mandatory=$true)][string]$Target,
 [Parameter(Mandatory=$true)][string]$OutputRoot,
 [string]$OriginalClient,[string]$ServerUrl='http://127.0.0.1:8091',
 [string]$ServerArchive,[string]$BaselineArchive,[string]$Media
)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'tools/modules/Install.ps1') -Module 'season-pass' @PSBoundParameters
