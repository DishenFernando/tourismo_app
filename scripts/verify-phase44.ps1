$ErrorActionPreference = 'Stop'
$compose = @('compose', '--env-file', '.env', '-f', 'infra/compose.yaml')
Write-Host 'Tourismo Phase 4.4 read-only verification'
& docker @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is unavailable' }
$rev = & docker @compose exec -T app alembic current 2>&1
if ($LASTEXITCODE -ne 0 -or ($rev -join "`n") -notmatch '0013_onboarding_media_ux') { throw "Migration not applied: $rev" }
$health = Invoke-RestMethod 'http://localhost:8000/api/v1/health/ready'
if ($health.status -ne 'ok') { throw 'Backend is not ready' }
# Check that original public destination discovery remains available.
$destinations = Invoke-RestMethod 'http://localhost:8000/api/v1/destinations'
if ($null -eq $destinations) { throw 'Destination API unavailable' }
# No images or business rows are created by the smoke check.
$tables = & docker @compose exec -T db psql -U tourismo -d tourismo -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='destination_image_blobs'"
if ($LASTEXITCODE -ne 0 -or ($tables -join "").Trim() -ne '1') { throw 'Media table missing' }
$columns = & docker @compose exec -T db psql -U tourismo -d tourismo -Atc "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='vendor_organizations' AND column_name IN ('province','district','operating_address') AND is_nullable='YES'"
if ($LASTEXITCODE -ne 0 -or ($columns -join "").Trim() -ne '3') { throw 'Progressive onboarding schema not applied' }
Write-Host 'PASS: database, migration, public discovery, and progressive draft schema (read-only).'
