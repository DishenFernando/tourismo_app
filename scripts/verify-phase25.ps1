# Tourismo Phase 2.5 read-only verification; execute from the repository root.
$ErrorActionPreference = 'Stop'
$compose = @('--env-file', '.env', '-f', 'infra/compose.yaml')

Write-Host '=== Tourismo Phase 2.5 checks ==='
docker compose @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is unavailable or the stack is not running.' }

$ready = Invoke-RestMethod 'http://localhost:8000/api/v1/health/ready'
Write-Host ('Readiness endpoint returned: ' + ($ready | ConvertTo-Json -Compress))

$version = docker compose @compose exec -T db psql -U tourismo -d tourismo -tAc 'SELECT version_num FROM alembic_version;'
if ($LASTEXITCODE -ne 0) { throw 'Could not query Alembic revision in PostgreSQL.' }
$version = ($version | Out-String).Trim()
if ($version -ne '0007_pilot_destination_guides') { throw "Unexpected migration revision: $version" }
Write-Host "Alembic revision OK: $version"

foreach ($slug in @('kandy','galle','anuradhapura','sigiriya','nuwara-eliya')) {
    $guide = Invoke-RestMethod "http://localhost:8000/api/v1/destinations/$slug/guide"
    $pois = @(Invoke-RestMethod "http://localhost:8000/api/v1/destinations/$slug/pois")
    if (-not $guide.overview -or -not $guide.source.url) {
        throw "Missing source-referenced public guide for: $slug"
    }
    Write-Host ("{0}: {1} attractions visible, guide status={2}" -f $slug, $pois.Count, $guide.content_status)
}

try {
    Invoke-WebRequest 'http://localhost:8000/api/v1/admin/content-audit' -UseBasicParsing | Out-Null
    throw 'SECURITY CHECK FAILED: admin audit accessible to guests!'
}
catch {
    if ($_.Exception.Response.StatusCode -ne 401) { throw }
    Write-Host 'Admin access check passed (HTTP 401 for guests)'
}
Write-Host 'Phase 2.5 local smoke checks passed.'
