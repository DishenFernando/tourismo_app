param([string]$Root='.', [string]$BaseUrl='http://localhost:8000')
$ErrorActionPreference='Stop'
$rootPath=(Resolve-Path $Root).Path
$required=@(
  'apps/api/migrations/versions/0020_travel_email.py',
  'apps/api/tourismo/navigation/routes.py',
  'apps/api/tourismo/notifications/mail_worker.py',
  'apps/web/src/features/TravelDirections.tsx',
  'infra/compose.email-worker.yaml'
)
foreach ($file in $required) {
  if (-not (Test-Path (Join-Path $rootPath $file))) { throw "Missing Phase 10B file: ${file}" }
}
Write-Host 'PASS: Phase 10B feature files present.'
try {
  $response=Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/health/ready" -TimeoutSec 8
  Write-Host 'PASS: API readiness endpoint responds.'
} catch { throw 'Tourismo API health is unavailable; check Docker app logs.' }
$head = docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
if ($LASTEXITCODE -ne 0) { throw 'Could not read Alembic version' }
if (($head -join '').Trim() -ne '0020_travel_email') { throw "Expected 0020_travel_email, got: $head" }
Write-Host 'PASS: 0020_travel_email migration.'
$tables = docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('email_preferences','email_outbox','email_broadcast_jobs');"
if ($LASTEXITCODE -ne 0 -or ($tables -join '').Trim() -ne '3') { throw 'Email tables are not ready' }
Write-Host 'PASS: Three durable-email tables present.'
Write-Host 'MANUAL: Verify GPS permission, Google route links, signed-in email preferences, and provider delivery with a test account.'
Write-Host 'NOTE: A passing verifier does NOT mean a Resend domain, worker, mail/webhook delivery or routing API is configured.'
