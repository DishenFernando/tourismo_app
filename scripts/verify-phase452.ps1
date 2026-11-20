# Tourismo Phase 4.5 Part 2: read-only verification. Compatible with Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'
$compose = @('--env-file', '.env', '-f', 'infra/compose.yaml')
Write-Host 'Tourismo Phase 4.5 Part 2 - read-only verification'
& docker compose @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is not available' }
# Query the migration directly via psql to avoid Alembic INFO logging on stderr.
$revision = & docker compose @compose exec -T db psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM alembic_version;'
if ($LASTEXITCODE -ne 0) { throw 'Could not query migration version' }
$version = ($revision | Out-String).Trim()
Write-Host "Applied migration: $version"
if ($version -ne '0014_vendor_experience') { throw 'Expected 0014_vendor_experience' }
$table = & docker compose @compose exec -T db psql -U tourismo -d tourismo -At -c "SELECT to_regclass('public.service_listing_image_blobs') IS NOT NULL;"
if ($LASTEXITCODE -ne 0 -or ($table | Out-String).Trim() -ne 't') { throw 'Service photo storage table not found' }
$ready = Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/health/ready' -TimeoutSec 15
if ($ready.status -ne 'ok') { throw 'Tourismo backend is not ready' }
Write-Host 'PASS: Docker, database revision, photo schema and backend readiness.'
Write-Host 'Manual checks remain for real vendor uploads, Clerk email invitations and admin review.'
