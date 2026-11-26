$ErrorActionPreference = 'Stop'
$compose = @('compose','--env-file','.env','-f','infra/compose.yaml')
Write-Host 'Tourismo Phase 5.1 + location-link read-only verification'
& docker @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is not available or services are stopped.' }

$revision = & docker @compose exec -T db psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
if ($LASTEXITCODE -ne 0) { throw 'Could not read the Alembic revision from PostgreSQL.' }
if (($revision -join ' ').Trim() -ne '0015_location_links') {
    throw "Expected 0015_location_links; got: $revision"
}
Write-Host "Migration: $revision"

$ready = Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/health/ready' -TimeoutSec 15
if ($ready.status -ne 'ok') { throw 'Backend is not ready.' }
$mapConfig = Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/map/config' -TimeoutSec 15
# On Windows PowerShell 5.1, Invoke-RestMethod may return a JSON list as one
# nested array when wrapped with @(...).  Request the raw JSON and deserialize
# it under an object property to preserve array boundaries for 0, 1, or N pins.
$mapResponse = Invoke-WebRequest -Uri 'http://localhost:8000/api/v1/map/points' -UseBasicParsing -TimeoutSec 30
$mapResult = ConvertFrom-Json -InputObject ('{"points":' + $mapResponse.Content + '}')
if ($null -eq $mapResult.points -or $mapResult.points -isnot [System.Array]) {
    throw 'Map API must return a JSON array of marker objects.'
}
$points = $mapResult.points
foreach ($p in $points) {
    if ($p.kind -notin @('destination','attraction','service')) { throw "Unexpected marker kind '$($p.kind)' for marker '$($p.id)'." }
    if ($null -eq $p.latitude -or $null -eq $p.longitude -or $p.latitude -lt -90 -or $p.latitude -gt 90 -or $p.longitude -lt -180 -or $p.longitude -gt 180) { throw "Invalid coordinates for marker '$($p.id)'." }
    if ($p.detail_path -notmatch '^/(destinations|listings)/') { throw "Invalid public detail link for marker '$($p.id)'." }
    if ($p.id -match 'tourismo-demo-') { throw "Demo marker '$($p.id)' leaked into public map." }
}
Write-Host "PASS: API ready; $($points.Count) public mapped points; tile URL configured: $([bool]$mapConfig.tile_url)"
Write-Host 'Review /map in the browser and test pin/list interactions before Phase 5.1 acceptance.'

# The share-link resolver is authenticated; anonymous requests must not be accepted.
$uri = 'http://localhost:8000/api/v1/map/resolve-location'
$body = '{"url":"https://www.openstreetmap.org/?mlat=6.9271&mlon=79.8612"}'
try {
    $unexpected = Invoke-WebRequest -Uri $uri -Method Post -ContentType 'application/json' `
        -Body $body -TimeoutSec 15 -UseBasicParsing
    throw "SECURITY FAIL: unauthenticated map-link import returned $($unexpected.StatusCode)"
} catch [System.Net.WebException] {
    if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 401) {
        throw "Expected 401 from unauthenticated map-link import; got: $($_.Exception.Message)"
    }
}
Write-Host 'PASS: shared-link resolver rejects anonymous requests (HTTP 401).'
Write-Host 'EDITOR ACCEPTANCE: Paste and confirm a maps.app.goo.gl pin in Content Studio; save destination location; verify /map shows it.'
