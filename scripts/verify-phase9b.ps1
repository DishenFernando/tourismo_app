param([string]$Root = '.',[string]$BaseUrl = 'http://localhost:8000')
$ErrorActionPreference = 'Stop'
$path = (Resolve-Path $Root).Path
$required = @(
  'apps/web/src/features/NavigationPolish.css',
  'apps/web/src/features/TranslationWorkbench.tsx',
  'scripts/phase9b_release/diagnose_editorial_loading.py',
  'docs/PHASE9B_NAV_TRANSLATION_START.md'
)
foreach ($item in $required) {
  if (-not (Test-Path (Join-Path $path $item))) {throw "Missing Phase 9B file: $item"}
}
$app = Get-Content (Join-Path $path 'apps/web/src/app/App.tsx') -Raw
$header = Get-Content (Join-Path $path 'apps/web/src/components/Header.tsx') -Raw
$chrome = Get-Content (Join-Path $path 'apps/web/src/features/SiteChrome.tsx') -Raw
if ($header -notmatch 'tourismo-navbar-shell' -or $app -notmatch '/admin/translation-workbench') {throw 'Phase 9B routes/navbar not wired'}
if ($chrome -notmatch 'tourismo-utility-bar' -or $chrome -notmatch 'Language coverage') {throw 'Phase 9B utility controls not wired'}
$rev = docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
if ($LASTEXITCODE -ne 0 -or ($rev -join '').Trim() -ne '0018_service_enquiries') {throw "Unexpected migration; expected 0018_service_enquiries, got $rev"}
try {
  $response = Invoke-WebRequest -Uri $BaseUrl -UseBasicParsing -TimeoutSec 10
  if ($response.StatusCode -ne 200) {throw "Homepage status $($response.StatusCode)"}
} catch {throw "Tourismo homepage unavailable: $($_.Exception.Message)"}
Write-Host 'PASS: Phase 9B-1 source, DB head, homepage and wiring checks.'
Write-Host 'MANUAL: Desktop/mobile nav, account menu, keyboard, translation workbench roles, 9A SEO, reviews, enquiries, map.'
Write-Host 'MANUAL: Investigate editorial-content banner with browser Network panel and script; not automatically fixed.'
