$ErrorActionPreference = 'Stop'
Write-Host 'Tourismo fictional demo — read-only checks' -ForegroundColor Cyan
$compose = @('--env-file', '.env', '-f', 'infra/compose.yaml')
docker compose @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is not available' }
$rev = docker compose @compose exec -T app alembic current
if ($LASTEXITCODE -ne 0) { throw 'Alembic query failed' }
$rev | Out-Host
if (-not ($rev -match '0010_service_listings')) { throw 'Expected Phase 4.1 0010_service_listings migration' }
$result = Invoke-RestMethod 'http://localhost:8000/api/v1/demo/status'
Write-Host "Demo preview enabled: $($result.enabled)"
if (-not $result.enabled) { throw 'Set APP_ENVIRONMENT=development and ENABLE_DEMO_CATALOG=true in .env; recreate app container' }
$list = Invoke-RestMethod 'http://localhost:8000/api/v1/demo/listings?limit=60'
Write-Host "Demo listings visible: $(@($list).Count)"
if (@($list).Count -ne 24) { throw 'Expected 24 fictional demo listing rows; apply the standalone SQL seed in DBeaver' }
if (@($list | Where-Object { $_.is_demo -ne $true -or $_.public_email -or $_.public_phone }).Count -gt 0) {
  throw 'Demo safety check failed (marker or contacts)'
}
Write-Host 'Demo preview safety checks passed.' -ForegroundColor Green
