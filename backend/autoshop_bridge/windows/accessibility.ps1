param([Parameter(Mandatory=$true)][string]$RequestBase64)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=New-Object Text.UTF8Encoding($false)
try {
 Add-Type -AssemblyName Accessibility
 Add-Type -ReferencedAssemblies Accessibility -Path @((Join-Path $PSScriptRoot 'grid_reader.cs'),(Join-Path $PSScriptRoot 'accessibility.cs'))
 $r=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($RequestBase64)) | ConvertFrom-Json
 if($r.action -eq 'prepare_initial_instance_step') {
  $value=[BridgeAccessibility]::PrepareInitialInstanceStep([long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.program,[string]$r.instance,[string]$r.instance_type,
   [int]$r.physical_rows,[int]$r.physical_row,[string[]]$r.expected_row,[string[]]$r.expected_names,[string]$r.step,[bool]$r.physical_select)
 } elseif($r.action -eq 'select_initial_instance') {
  $value=[BridgeAccessibility]::SelectInitialInstance([long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.program,[string]$r.instance,[string]$r.instance_type,
   [int]$r.physical_rows,[int]$r.physical_row,[string[]]$r.expected_row,[bool]$r.physical_select,[string[]]$r.expected_names)
 } elseif($r.action -eq 'instance_initial_page') {
  $value=[BridgeAccessibility]::ReadInitialPage([long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.instance,[int]$r.offset,[int]$r.limit)
 } elseif($r.action -eq 'instance_initial_step') {
  $initialColumn=1
  if($null -ne $r.PSObject.Properties['target_column']){$initialColumn=[int]$r.target_column}
  $value=[BridgeAccessibility]::InitialStep([long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.instance,[int]$r.physical_data_rows,[int]$r.physical_index,
   [string[]]$r.expected_root,[string[]]$r.expected_row,[string[]]$r.expected_before,[string[]]$r.expected_after,
   [string]$r.step,[int]$r.glyph_offset_x,$initialColumn)
 } elseif($r.action -eq 'instance_grid_page') {
  $value=[BridgeAccessibility]::ReadInstancePage([long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.program,[int]$r.offset,[int]$r.limit)
 } elseif($r.action -eq 'grid_diagnostic_page') {
  $value=[BridgeAccessibility]::ReadGridDiagnosticPage([long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.program,[int]$r.offset,[int]$r.limit)
 } elseif($r.action -eq 'grid_prepare_root_step') {
  $value=[BridgeAccessibility]::PrepareGridRootStep([long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.program,[int]$r.physical_rows,[int]$r.physical_row,
   [string[]]$r.expected_row,[string]$r.before_full_name,[string]$r.after_full_name,[string]$r.step,[int[]]$r.known_other_ids)
 } elseif($r.action -eq 'grid_cell_step') {
  $value=[BridgeAccessibility]::PrepareGridCellStep([long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.program,[int]$r.physical_rows,[int]$r.source_row,[int]$r.display_row,[int]$r.column_index,
   [string[]]$r.expected_source_row,[string[]]$r.expected_display_row,[string]$r.before_full_name,[string]$r.after_full_name,
   [string]$r.variable,[string]$r.expected,[bool]$r.spare,[string]$r.step)
 } else {
  $value=[BridgeAccessibility]::Run([string]$r.action,[long]$r.main,[long]$r.target,[int]$r.pid,
   [string]$r.project,[string]$r.program,[string]$r.variable,[string]$r.column,[string]$r.expected)
 }
 $response=@{status='ok';result=$value} | ConvertTo-Json -Depth 12 -Compress
 if([Text.Encoding]::UTF8.GetByteCount($response) -gt 8*1024*1024){throw 'Accessibility complete response exceeds 8 MiB; no fields were truncated'}
 $response
} catch {
 @{status='error';error=$_.Exception.Message} | ConvertTo-Json -Compress
 exit 1
}
