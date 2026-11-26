# Tourismo Phase 8 read-only verification; Windows PowerShell 5.1.
# No enquiry creation, messages, moderation, migrations, or destructive operations.
$ErrorActionPreference = 'Stop'
$base = 'http://localhost:8000'
Write-Host 'Tourismo Phase 8 — Tourist/Provider Enquiries (read-only checks)'

docker compose --env-file .env -f infra/compose.yaml ps
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose is unavailable.' }
$revision = docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
if ($LASTEXITCODE -ne 0 -or ($revision -join '').Trim() -ne '0018_service_enquiries') {
    throw "Expected migration 0018_service_enquiries; got: $revision"
}
$tables = docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('service_enquiries','service_enquiry_messages','service_enquiry_reports');"
if ($LASTEXITCODE -ne 0 -or ($tables -join '').Trim() -ne '3') {
    throw 'Phase 8 enquiry tables are missing.'
}
$ready = Invoke-RestMethod -Uri "$base/api/v1/health/ready" -TimeoutSec 20
if ($ready.status -ne 'ok') { throw 'Application readiness check failed.' }

function Assert-GuestForbidden([string]$path, [string]$method, [string]$body='') {
    $r = @{ Uri="$base$path"; Method=$method; TimeoutSec=15; UseBasicParsing=$true }
    if ($method -eq 'POST') { $r['ContentType']='application/json'; $r['Body']=$body }
    try {
        Invoke-WebRequest @r | Out-Null
        throw "SECURITY FAIL: Guest $method $path was allowed"
    } catch [System.Net.WebException] {
        if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 401) {
            throw "Expected guest 401 for $method $path, got $($_.Exception.Message)"
        }
    }
}
$fake='00000000-0000-0000-0000-000000000001'
$org='00000000-0000-0000-0000-000000000002'
Assert-GuestForbidden '/api/v1/enquiries' 'GET'
Assert-GuestForbidden "/api/v1/enquiries/$fake" 'GET'
Assert-GuestForbidden '/api/v1/enquiries/listings/not-a-real-service' 'POST' '{"subject":"Availability details","message":"Could you share options and an indicative quotation?"}'
Assert-GuestForbidden "/api/v1/enquiries/$fake/messages" 'POST' '{"body":"Requesting more information"}'
Assert-GuestForbidden "/api/v1/enquiries/$fake/withdraw" 'POST'
Assert-GuestForbidden "/api/v1/enquiries/$fake/reports" 'POST' '{"reason":"spam","explanation":"Please review the conversation for possible spam."}'
Assert-GuestForbidden "/api/v1/vendor/organizations/$org/enquiries" 'GET'
Assert-GuestForbidden "/api/v1/vendor/organizations/$org/enquiries/$fake" 'GET'
Assert-GuestForbidden "/api/v1/vendor/organizations/$org/enquiries/$fake/messages" 'POST' '{"body":"Replying to the customer inquiry"}'
Assert-GuestForbidden '/api/v1/admin/enquiry-reports' 'GET'
Assert-GuestForbidden "/api/v1/admin/enquiry-reports/$fake/thread" 'GET'
Assert-GuestForbidden "/api/v1/admin/enquiry-reports/$fake/decision" 'POST' '{"decision":"block_thread","reason":"Confirmed abuse requires closing the conversation."}'
Write-Host 'PASS: Migration 0017, all three enquiry tables, app readiness, private guest boundaries.'
Write-Host 'MANUAL ACCEPTANCE: Tourist A and B isolation; vendor A and B isolation; full create/reply/withdraw/close/report/admin block workflow.'
Write-Host 'MANUAL ACCEPTANCE: Verify reviews, map, saved trips, budgets and mobile UI remain working.'
