# Tourismo Phase 5.3 - read-only API, trip validation, and map reference checks.
# Windows PowerShell 5.1 compatible. Run from repository root; no DB writes.
$ErrorActionPreference = 'Stop'
Write-Host 'Tourismo Phase 5.3 read-only verification'
$previous = Join-Path $PSScriptRoot 'verify-phase52.ps1'
& powershell -NoProfile -ExecutionPolicy Bypass -File $previous
if ($LASTEXITCODE -ne 0) { throw 'Previous Phase 5.2 verification failed. Do not proceed.' }

$base = 'http://localhost:8000'
$raw = Invoke-WebRequest -Uri "$base/api/v1/map/points" -UseBasicParsing -TimeoutSec 30
$wrapped = ConvertFrom-Json -InputObject ('{"points":' + $raw.Content + '}')
if ($wrapped.points -isnot [System.Array]) { throw 'Public map points must return a JSON array.' }
if ($wrapped.points.Count -gt 0) {
    $reference = [string]$wrapped.points[0].id
} else {
    $reference = 'destination:00000000-0000-0000-0000-000000000001'
    Write-Host 'INFO: No mapped points. Verifying a missing reference without creating map data.'
}
$body = @{place_ids=@($reference)} | ConvertTo-Json -Depth 4 -Compress
$resultRaw = Invoke-WebRequest -Uri "$base/api/v1/map/itinerary-places" -UseBasicParsing `
    -Method POST -ContentType 'application/json' -Body $body -TimeoutSec 30
$result = ConvertFrom-Json -InputObject ('{"places":' + $resultRaw.Content + '}')
if ($result.places -isnot [System.Array]) { throw 'Itinerary references must return a JSON array.' }
if ($wrapped.points.Count -gt 0) {
    if ($result.places.Count -ne 1 -or $result.places[0].id -ne $reference) {
        throw 'Itinerary reference did not match the public map point.'
    }
}
foreach ($place in $result.places) {
    if ($place.kind -notin @('destination','attraction','service') -or
        $place.detail_path -notmatch '^/(destinations|listings)/') { throw 'Invalid public place details.' }
    if ($place.PSObject.Properties.Name -contains 'public_email' -or
        $place.PSObject.Properties.Name -contains 'vendor_evidence') { throw 'Sensitive provider data exposed.' }
}

# The guest preview accepts the new optional place_id without creating a trip.
$trip = @{destination_slug='nuwara-eliya';title='Phase 5.3 test trip';adults=2;children_ages=@();
          itinerary=@(@{day=1;title='Mapped stop';note='Guest preview';place_id=$reference});budget_items=@()}
$preview = Invoke-RestMethod -Uri "$base/api/v1/trips/preview" -Method POST `
    -ContentType 'application/json' -Body ($trip | ConvertTo-Json -Depth 8 -Compress) -TimeoutSec 30
if ($null -eq $preview.expected_minor -or $preview.currency -ne 'LKR') {
    throw 'Trip preview failed with linked itinerary stop.'
}
try {
    Invoke-WebRequest -Uri "$base/api/v1/map/itinerary-places" -Method POST `
        -UseBasicParsing -ContentType 'application/json' -Body '{"place_ids":["not-an-id"]}' `
        -TimeoutSec 15 | Out-Null
    throw 'Malformed public reference should have been rejected.'
} catch [System.Net.WebException] {
    if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 422) {
        throw "Expected HTTP 422 for malformed reference: $($_.Exception.Message)"
    }
}
Write-Host "PASS: Phase 5.3 public itinerary-place resolution; $($result.places.Count) available points."
Write-Host 'PASS: Guest preview accepts stable public-place references; invalid IDs rejected.'
Write-Host 'MANUAL ACCEPTANCE: /map or /nearby -> Add to trip -> /plan -> day/notes/order/map -> save/login -> /saved.'
Write-Host 'NOTE: Cloud-saved trips are read-only snapshots; lines are not driving routes.'
