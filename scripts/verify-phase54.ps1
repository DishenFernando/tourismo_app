# Tourismo Phase 5.4 - bounded-map and geographic quality acceptance checks.
# Windows PowerShell 5.1 compatible; read-only. Does not change data or configuration.
param([string]$EditorToken = '')
$ErrorActionPreference = 'Stop'
Write-Host 'Tourismo Phase 5.4 read-only verification'
$previous = Join-Path $PSScriptRoot 'verify-phase53.ps1'
& powershell -NoProfile -ExecutionPolicy Bypass -File $previous
if ($LASTEXITCODE -ne 0) { throw 'Phase 5.3 checks failed. Verify earlier phases first.' }

$base = 'http://localhost:8000'
$uri = "$base/api/v1/map/viewport?south=5.5&west=79.4&north=10.1&east=82.1&kind=all&limit=20"
$viewport = Invoke-RestMethod -Uri $uri -TimeoutSec 30
if ($null -eq $viewport.points -or $null -eq $viewport.limit -or $null -eq $viewport.has_more) {
    throw 'Viewport must include points, has_more and limit.'
}
if ($viewport.limit -ne 20 -or @($viewport.points).Count -gt 20) {
    throw 'Viewport server must enforce the 20-point response cap.'
}
$ids = @{}
foreach ($point in $viewport.points) {
    if ($point.kind -notin @('destination','attraction','service') -or
        $point.detail_path -notmatch '^/(destinations|listings)/') {
        throw "Invalid visible public marker: $($point.id)"
    }
    if ($ids.ContainsKey([string]$point.id)) { throw 'Duplicate public map ID in viewport.' }
    $ids[[string]$point.id] = $true
    if ($point.PSObject.Properties.Name -contains 'public_email' -or
        $point.PSObject.Properties.Name -contains 'vendor_evidence') {
        throw 'Private provider information is exposed in viewport data.'
    }
}

# A filtered search must never include a different marker kind.
$services = Invoke-RestMethod -Uri "$base/api/v1/map/viewport?kind=service&limit=20" -TimeoutSec 30
foreach ($point in $services.points) {
    if ($point.kind -ne 'service') { throw 'Service filter leaked another marker type.' }
}

# Invalid bounds and oversized result requests must fail before expensive queries.
foreach ($suffix in @('?limit=251', '?south=11&north=5')) {
    try {
        Invoke-WebRequest -Uri "$base/api/v1/map/viewport$suffix" -UseBasicParsing -TimeoutSec 15 | Out-Null
        throw "Invalid viewport unexpectedly succeeded: $suffix"
    } catch [System.Net.WebException] {
        if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 422) {
            throw "Expected HTTP 422 for $suffix; got $($_.Exception.Message)"
        }
    }
}

# This audit contains internal editorial records: it must not be available to guests.
try {
    Invoke-WebRequest -Uri "$base/api/v1/admin/geo-quality" -UseBasicParsing -TimeoutSec 15 | Out-Null
    throw 'Guest unexpectedly accessed editor-only location audit.'
} catch [System.Net.WebException] {
    if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 401) {
        throw "Expected guest HTTP 401 for geo-quality: $($_.Exception.Message)"
    }
}
if ($EditorToken) {
    $report = Invoke-RestMethod -Uri "$base/api/v1/admin/geo-quality" -Headers @{
        Authorization = "Bearer $EditorToken"
    } -TimeoutSec 30
    if ($null -eq $report.scanned -or $null -eq $report.sourced_mapped -or $null -eq $report.issues) {
        throw 'Editor location report has missing fields.'
    }
    Write-Host "PASS: Editor map source audit; $($report.scanned) records, $($report.sourced_mapped) sourced mapped."
}
Write-Host "PASS: Phase 5.4 viewport API, filtering, 20-place cap, guest privacy; $(@($viewport.points).Count) public points in limited view."
Write-Host 'MANUAL: /map -> zoom/pan/cluster/list/mobile; /admin/geo-quality -> review as editor.'
Write-Host 'NOTE: Coordinate sourcing and PostGIS performance require manual evidence and real data.'
