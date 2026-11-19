$ErrorActionPreference = 'Stop'
$compose = @('--env-file', '.env', '-f', 'infra/compose.yaml')
Write-Host 'Tourismo Phase 3.2 - read-only verification' -ForegroundColor Cyan
& docker compose @compose ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose unavailable' }
$heads = & docker compose @compose exec -T app alembic heads
if ($LASTEXITCODE -ne 0 -or ($heads -join ' ') -notmatch '0009_vendor_documents') { throw "Expected migration head 0009_vendor_documents. Actual: $heads" }
$current = & docker compose @compose exec -T app alembic current
if ($LASTEXITCODE -ne 0 -or ($current -join ' ') -notmatch '0009_vendor_documents') { throw "Migration not applied: $current" }
$health = Invoke-RestMethod 'http://localhost:8000/api/v1/health/live'
Write-Host "API health: $($health | ConvertTo-Json -Compress)"
$id = '00000000-0000-0000-0000-000000000000'
$unauthorized = & curl.exe -s -o NUL -w '%{http_code}' "http://localhost:8000/api/v1/vendor/organizations/$id/documents"
if ($unauthorized -ne '401') { throw "Anonymous document route returned $unauthorized; expected 401" }
$public = & curl.exe -s -o NUL -w '%{http_code}' 'http://localhost:8000/api/v1/destinations'
if ($public -ne '200') { throw "Guest discovery returned $public; expected 200" }
Write-Host 'PASS: Phase 3.2 migration, private documents, guest discovery and API health.' -ForegroundColor Green
