# Read-only smoke checks: execute from Tourismo repository root.
$ErrorActionPreference = 'Stop'
$compose = @('--env-file', '.env', '-f', 'infra/compose.yaml')
Write-Host '[1/5] Compose service status'
docker compose @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is not available' }
Write-Host '[2/5] Migration current'
docker compose @compose exec -T app alembic current
if ($LASTEXITCODE -ne 0) { throw 'Alembic current failed' }
Write-Host '[3/5] Migration head'
docker compose @compose exec -T app alembic heads
if ($LASTEXITCODE -ne 0) { throw 'Alembic heads failed' }
Write-Host '[4/5] Public listings, no login needed'
$items = Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/listings' -Method Get
Write-Host ('Visible published listings: ' + @($items).Count)
Write-Host '[5/5] Private admin endpoint must reject anonymous access'
try {
  Invoke-WebRequest -Uri 'http://localhost:8000/api/v1/admin/listings' -Method Get -UseBasicParsing | Out-Null
  throw 'FAIL: Anonymous user was allowed to read admin listing reviews'
} catch {
  if ($_.Exception.Response.StatusCode -ne [System.Net.HttpStatusCode]::Unauthorized) { throw }
  Write-Host 'PASS: anonymous admin request returned HTTP 401'
}
Write-Host 'Phase 4.1 smoke checks complete. Manual vendor/admin publication flow still requires testing.'
