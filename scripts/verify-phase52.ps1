# Tourismo Phase 5.2 - read-only acceptance verification (Windows PowerShell 5.1+).
# Run from the Tourismo project root. Does not modify Docker, DB or data.
$ErrorActionPreference = 'Stop'
Write-Host 'Tourismo Phase 5.2 read-only verification'
$previous = Join-Path $PSScriptRoot 'verify-location-links.ps1'
& powershell -NoProfile -ExecutionPolicy Bypass -File $previous
if ($LASTEXITCODE -ne 0) { throw 'Phase 5.1 location-link checks failed.' }

$base = 'http://localhost:8000'
$source = Invoke-WebRequest -Uri "$base/api/v1/map/points" -UseBasicParsing -TimeoutSec 30
$all = ConvertFrom-Json -InputObject ('{"points":' + $source.Content + '}')
if ($null -eq $all.points -or $all.points -isnot [System.Array]) {
    throw 'Map points endpoint must return a JSON array.'
}
if ($all.points.Count -eq 0) {
    Write-Host 'INFO: No mapped public points. Nearby endpoint requires an actual mapped center.'
    Write-Host 'Add a sourced map coordinate to a public destination/attraction, then rerun.'
    exit 0
}

$origin = $all.points[0]
$lat = [Convert]::ToString([double]$origin.latitude, [Globalization.CultureInfo]::InvariantCulture)
$lon = [Convert]::ToString([double]$origin.longitude, [Globalization.CultureInfo]::InvariantCulture)
$url = "$base/api/v1/map/nearby?near_lat=$lat&near_lon=$lon&radius_km=100&limit=60"
$result = Invoke-RestMethod -Uri $url -TimeoutSec 30
if ($null -eq $result.center -or $null -eq $result.radius_km) {
    throw 'Nearby response is missing center/radius metadata.'
}
if ([math]::Abs([double]$result.center.latitude - [double]$lat) -gt 0.00001 -or
    [math]::Abs([double]$result.center.longitude - [double]$lon) -gt 0.00001) {
    throw 'Nearby response center does not match the selected point.'
}
if ($result.radius_km -ne 100 -or $null -eq $result.points) {
    throw 'Nearby response has invalid radius or missing points.'
}
$previousDistance = -1.0
foreach ($point in $result.points) {
    if ($null -eq $point -or $point.kind -notin @('destination', 'attraction', 'service')) {
        throw 'Unexpected nearby marker kind.'
    }
    if ($null -eq $point.distance_km -or $point.distance_km -lt 0 -or $point.distance_km -gt 100.01) {
        throw "Invalid straight-line distance for $($point.id)."
    }
    if ($point.distance_km -lt $previousDistance) {
        throw 'Nearby points are not sorted by distance.'
    }
    if ($point.detail_path -notmatch '^/(destinations|listings)/') {
        throw "Unexpected public detail path for $($point.id)."
    }
    if ($point.PSObject.Properties.Name -contains 'public_email' -or
        $point.PSObject.Properties.Name -contains 'vendor_evidence') {
        throw 'Sensitive listing fields were exposed in nearby results.'
    }
    $previousDistance = [double]$point.distance_km
}

try {
    Invoke-WebRequest -Uri "$base/api/v1/map/nearby?near_lat=$lat&near_lon=$lon&radius_km=101" `
        -UseBasicParsing -TimeoutSec 15 | Out-Null
    throw 'Expected 422 for unsupported radius but request succeeded.'
} catch [System.Net.WebException] {
    if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 422) {
        throw "Expected 422 for radius >100 km; got $($_.Exception.Message)"
    }
}
Write-Host "PASS: Phase 5.2 nearby API and bounds verified; $($result.points.Count) results within 100 km."
Write-Host 'MANUAL ACCEPTANCE: Open http://localhost:8000/nearby and test centers, radius, categories and map/list selection.'
Write-Host 'NOTE: Straight-line distances are not road directions or estimated travel time.'
