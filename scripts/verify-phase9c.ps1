# Tourismo Phase 9C — read-only verification (Windows PowerShell 5.1+)
param([string]$BaseUrl = 'http://localhost:8000')
$ErrorActionPreference = 'Stop'
$base = $BaseUrl.TrimEnd('/')

function Assert-Status([string]$method, [string]$path, [int]$expected) {
    $code = 0
    try {
        $response = Invoke-WebRequest -Uri ($base + $path) -Method $method -UseBasicParsing -ErrorAction Stop
        $code = [int]$response.StatusCode
    } catch {
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $code = [int]$_.Exception.Response.StatusCode
        } else { throw "Unable to reach ${path}: $($_.Exception.Message)" }
    }
    if ($code -ne $expected) { throw "Expected HTTP $expected for ${method} ${path}, received $code" }
    Write-Host "PASS: $method $path => $code"
}

Assert-Status 'GET' '/api/v1/health/live' 200
Assert-Status 'GET' '/api/v1/health/ready' 200
Assert-Status 'GET' '/api/v1/notifications' 401
Assert-Status 'GET' '/api/v1/notifications/unread-count' 401
Assert-Status 'POST' '/api/v1/notifications/read-all' 401
Assert-Status 'POST' '/api/v1/admin/announcements' 401
Assert-Status 'POST' '/api/v1/admin/customer-reviews/00000000-0000-4000-8000-000000000000/remove' 401

$compose = @('--env-file','.env','-f','infra/compose.yaml','exec','-T','db',
             'psql','-U','tourismo','-d','tourismo','-At','-c',
             'SELECT version_num FROM public.alembic_version;')
$revision = & docker compose @compose
if ($LASTEXITCODE -ne 0) { throw 'Unable to read Alembic version' }
if (($revision -join '').Trim() -ne '0019_notifications_trust') {
    throw "Expected migration 0019_notifications_trust, got: $revision"
}
Write-Host 'PASS: Alembic migration 0019_notifications_trust'

$tables = & docker compose --env-file .env -f infra/compose.yaml exec -T db `
   psql -U tourismo -d tourismo -At -c `
   "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('user_notifications','platform_announcements','announcement_reads');"
if ($LASTEXITCODE -ne 0 -or ($tables -join '').Trim() -ne '3') {
    throw 'Notification tables are missing; expected three new public tables'
}
Write-Host 'PASS: three notification tables exist'
Write-Host 'NEXT: Browser-test two distinct tourist accounts, one vendor owner, and an admin release announcement.'
