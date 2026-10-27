param([Parameter(Mandatory=$true)][string]$RequestBase64)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
try {
 Add-Type -AssemblyName Accessibility
 Add-Type -ReferencedAssemblies Accessibility -Path @((Join-Path $PSScriptRoot 'grid_reader.cs'),(Join-Path $PSScriptRoot 'accessibility.cs'))
 $r=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($RequestBase64)) | ConvertFrom-Json
 if($r.action -eq 'instance_grid_page') {
  $value=[BridgeAccessibility]::ReadInstancePage([long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.program,[int]$r.offset,[int]$r.limit)
 } else {
  $value=[BridgeAccessibility]::Run([string]$r.action,[long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.program,[string]$r.variable,[string]$r.column,[string]$r.expected)
 }
 @{status='ok';result=$value} | ConvertTo-Json -Depth 12 -Compress
} catch {
 @{status='error';error=$_.Exception.Message} | ConvertTo-Json -Compress
 exit 1
}
