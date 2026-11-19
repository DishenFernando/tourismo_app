# Run from the Tourismo repository root after `docker compose ... up --build -d`.
# Read-only checks. Never deletes data, writes secrets, or grants roles.
$ErrorActionPreference = 'Stop'
$compose = @('--env-file', '.env', '-f', 'infra/compose.yaml')

Write-Host '1. Docker container status'
docker compose @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose status failed.' }

Write-Host '2. API readiness'
$health = Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/health/ready'
if ($health.status -ne 'ok') { throw 'FastAPI is not ready.' }

Write-Host '3. Public guest API and destination content'
$places = @(Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/destinations')
if ($places.Count -lt 5) { throw "Unexpected public catalog count: $($places.Count)" }
Write-Host "Public destinations: $($places.Count)"
$guide = Invoke-RestMethod -Uri 'http://localhost:8000/api/v1/destinations/galle/guide'
Write-Host "Galle guide content state: $($guide.content_status)"

Write-Host '4. Alembic migration version'
$version = docker compose @compose exec -T db psql -U tourismo -d tourismo -tAc 'SELECT version_num FROM alembic_version'
if ($LASTEXITCODE -ne 0) { throw 'Could not read Alembic version.' }
$version = ($version | Out-String).Trim()
if ($version -ne '0006_editorial_quality') { throw "Expected 0006_editorial_quality, got $version" }
Write-Host "Migration: $version"

Write-Host '5. Database counts (read-only)'
docker compose @compose exec -T db psql -U tourismo -d tourismo -c 'SELECT content_status, COUNT(*) FROM destinations GROUP BY content_status ORDER BY content_status;'
if ($LASTEXITCODE -ne 0) { throw 'Database catalog query failed.' }

Write-Host '6. Unauthenticated admin endpoints must be protected'
try {
    Invoke-WebRequest -Uri 'http://localhost:8000/api/v1/admin/content-audit' -ErrorAction Stop | Out-Null
    throw 'SECURITY FAILURE: anonymous request accessed admin audit'
} catch {
    if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) {
        Write-Host 'Admin content audit rejects anonymous access (401)'
    } else { throw }
}
Write-Host 'Public smoke tests passed. Clerk role, edit/approval and ownership tests still require a signed-in browser session.'
