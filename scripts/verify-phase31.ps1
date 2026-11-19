# Read-only Phase 3.1 verification. Run from the repository root.
$ErrorActionPreference = 'Stop'
$compose = @('--env-file','.env','-f','infra/compose.yaml')
Write-Host 'Checking Tourismo Docker containers...'
docker compose @compose ps
Write-Host 'Checking Alembic revision...'
docker compose @compose exec -T app alembic current
Write-Host 'Checking Alembic heads...'
docker compose @compose exec -T app alembic heads
Write-Host 'Checking health...'
Invoke-RestMethod 'http://localhost:8000/api/v1/health/ready' | ConvertTo-Json
Write-Host 'Checking unprivileged vendor endpoints reject anonymous access...'
foreach ($path in @('/api/v1/vendor/organizations','/api/v1/admin/vendor-verifications')) {
    $code = & curl.exe -s -o NUL -w '%{http_code}' ("http://localhost:8000" + $path)
    if ($LASTEXITCODE -ne 0 -or $code -ne '401') {
        throw "Expected 401 for $path, got $code"
    }
    Write-Host "$path -> 401 (expected)"
}
Write-Host 'Confirm migration 0008_vendor_onboarding and verify owner/admin flows in the browser.'
