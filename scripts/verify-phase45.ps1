# Read-only Phase 4.5 smoke test. Safe for existing databases.
$ErrorActionPreference = 'Stop'
$compose = @('compose', '--env-file', '.env', '-f', 'infra/compose.yaml')
Write-Host 'Tourismo Phase 4.5 read-only verification'
& docker @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose status check failed.' }
$rev = (& docker @compose exec -T db psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM alembic_version;' | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not read database migration.' }
Write-Host "Applied migration: $rev"
if ($rev -ne '0013_onboarding_media_ux') { throw 'Phase 4.4 baseline migration 0013 is required; Phase 4.5 does not add a new migration.' }
$ready = Invoke-RestMethod 'http://localhost:8000/api/v1/health/ready'
Write-Host 'Readiness endpoint responded.'
# Auth is mandatory on quick draft creation. This request intentionally omits a Bearer token.
$org = '00000000-0000-0000-0000-000000000000'
$code = (& curl.exe -s -o NUL -w '%{http_code}' -X POST "http://localhost:8000/api/v1/vendor/organizations/$org/listings/quick-start" -H 'Content-Type: application/json' --data '{"title":"Security smoke test"}' | Out-String).Trim()
if ($LASTEXITCODE -ne 0) { throw 'HTTP authorization check failed to run.' }
if ($code -ne '401') { throw "Quick-start endpoint did not reject an anonymous request (status: $code)." }
Write-Host 'PASS: PostgreSQL migration, readiness, and private quick-start authorization checks.'
Write-Host 'Next: sign in as vendor and try saving a title-only draft at /vendor/listings.'
