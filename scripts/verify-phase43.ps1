$ErrorActionPreference = 'Stop'
$compose = @('compose', '--env-file', '.env', '-f', 'infra/compose.yaml')
Write-Host 'Tourismo Phase 4.3 read-only smoke test'
& docker @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose unavailable' }
$rev = & docker @compose exec -T app alembic current 2>&1
if ($LASTEXITCODE -ne 0) { throw "Could not inspect Alembic: $rev" }
if (($rev -join "`n") -notmatch '0012_listing_discovery_indexes') { throw "Wrong Alembic revision: $rev" }
$health = Invoke-RestMethod 'http://localhost:8000/api/v1/health/ready'
if ($health.status -ne 'ok') { throw 'API not ready' }
# Requests must fail validation before opening expensive search queries.
$bad = @(
  'http://localhost:8000/api/v1/listings?near_lat=7.2',
  'http://localhost:8000/api/v1/listings?category=restaurant&adults=2',
  'http://localhost:8000/api/v1/listings?near_lat=7&near_lon=80&radius_km=101'
)
foreach ($url in $bad) {
  $status = 0
  try { $resp = Invoke-WebRequest -Uri $url -UseBasicParsing; $status = [int]$resp.StatusCode }
  catch [System.Net.WebException] {
    if ($null -eq $_.Exception.Response) { throw }
    $status = [int]$_.Exception.Response.StatusCode
  }
  if ($status -ne 422) { throw "Expected 422 for $url; got $status" }
}
$results = Invoke-RestMethod 'http://localhost:8000/api/v1/listings?destination=kandy&limit=24'
if ($null -ne $results) {
  $list = @($results)
  if (@($list | Where-Object { $_.status -ne 'published' -or $_.is_demo -eq $true }).Count -gt 0) {
    throw 'Public API unexpectedly exposed a non-published/demo listing'
  }
}
Write-Host 'PASS: migration, health, query validation and public listing shape. No DB writes performed.'
