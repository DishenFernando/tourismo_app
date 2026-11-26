# Tourismo pre-Phase-5 read-only checks. PowerShell 5.1 compatible.
$ErrorActionPreference = 'Stop'
$compose = @('--env-file', '.env', '-f', 'infra/compose.yaml')
Write-Host 'Tourismo Pre-Phase-5 Verification (read-only)' -ForegroundColor Cyan
& docker compose @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose status check failed' }
$rev = & docker compose @compose exec -T db psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
if ($LASTEXITCODE -ne 0) { throw 'Migration query failed' }
Write-Host "Migration: $rev"
if (($rev | Out-String).Trim() -ne '0014_vendor_experience') { throw 'Expected Alembic 0014_vendor_experience; inspect migrations' }
$query = @'
SELECT 'published_by_business_status|' || o.verification_state || '|' || count(*)
FROM public.service_listings l JOIN public.vendor_organizations o ON o.id = l.organization_id
WHERE l.status = 'published' GROUP BY o.verification_state ORDER BY o.verification_state;
'@
& docker compose @compose exec -T db psql -U tourismo -d tourismo -At -c $query
if ($LASTEXITCODE -ne 0) { throw 'Listing status query failed' }
try {
  $health = Invoke-RestMethod 'http://localhost:8000/api/v1/health/ready'
  Write-Host 'Readiness endpoint responded.' -ForegroundColor Green
  $null = Invoke-RestMethod 'http://localhost:8000/api/v1/listings'
  Write-Host 'Public listing API responded.' -ForegroundColor Green
} catch { throw "HTTP verification failed: $($_.Exception.Message)" }
Write-Host 'PASS: Services, migration and public API checked. Complete manual badge/approval tests in docs.' -ForegroundColor Green
