# Tourismo Phase 4.2 - read-only smoke test. Never modifies the database.
$ErrorActionPreference = 'Stop'
$compose = @('--env-file', '.env', '-f', 'infra/compose.yaml')
Write-Host 'TOURISMO Phase 4.2 verification'
docker compose @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose unavailable' }
$head = docker compose @compose exec -T app alembic current
if ($LASTEXITCODE -ne 0 -or (($head | Out-String) -notmatch '0011_advanced_listings')) {
    throw 'Expected migration 0011_advanced_listings is not active'
}
$health = Invoke-RestMethod 'http://localhost:8000/api/v1/health/ready'
if ($health.status -ne 'ok') { throw 'Backend is not ready' }
$null = Invoke-RestMethod 'http://localhost:8000/api/v1/listings?province=Central'
$null = Invoke-RestMethod 'http://localhost:8000/api/v1/demo/status'
# Anonymous modifications MUST remain blocked.
$code = curl.exe -sS -o NUL -w '%{http_code}' 'http://localhost:8000/api/v1/admin/listings/revisions'
if ($code -ne '401') { throw "Anonymous admin revision access unexpectedly returned $code" }
Write-Host 'PASS: migration, readiness, public province filter, demo configuration and admin access control.'
Write-Host 'Next: manually check family suitability on a real published accommodation listing and admin revision approval.'
