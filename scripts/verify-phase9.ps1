# Tourismo Phase 9A read-only local source/HTTP verifier; Windows PowerShell 5.1 compatible.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
if (-not $root) { throw 'Unable to resolve repository root.' }
$required = @(
    'apps/web/src/i18n/LocaleProvider.tsx',
    'apps/web/src/features/SiteChrome.tsx',
    'apps/web/src/features/AccessibilityPage.tsx',
    'scripts/audit-phase9-content.py',
    'docs/PHASE9_CONTENT_LOCALIZATION_ACCESSIBILITY.md'
)
foreach ($relative in $required) {
    $path = Join-Path $root ($relative.Replace('/', [IO.Path]::DirectorySeparatorChar))
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing Phase 9A source: ${relative}" }
}
$app = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'apps/web/src/app/App.tsx')
$header = Get-Content -Raw -Encoding UTF8 (Join-Path $root 'apps/web/src/components/Header.tsx')
if ($app -notmatch 'LocaleProvider' -or $app -notmatch 'tourismo-content' -or $app -notmatch 'path="/accessibility"') {
    throw 'Phase 9A route, skip target or provider not wired into App.tsx'
}
if ($header -notmatch 'navLabel') { throw 'Localized navigation not wired into Header.tsx' }
Write-Host 'PASS: Phase 9A source wiring and expected files detected.'
try {
    $resp = Invoke-WebRequest -Uri 'http://localhost:8000/api/v1/health/ready' -UseBasicParsing -TimeoutSec 8
    if ($resp.StatusCode -ne 200) { throw "Unexpected readiness response: $($resp.StatusCode)" }
    Write-Host 'PASS: local API readiness endpoint returned HTTP 200.'
} catch {
    Write-Warning 'Local HTTP readiness was not verified. Start Docker Compose and retry.'
}
Write-Host 'MANUAL: npm run build, keyboard Tab -> Skip to content -> focused main area.'
Write-Host 'MANUAL: Change language EN/SI/TA; refresh; confirm persistence and navigation labels.'
Write-Host 'MANUAL: Check private screens, map, reviews, photo moderation, enquiries and mobile layout.'
Write-Host 'MANUAL: Inspect document title, canonical/robots and screen reader announcement on navigation.'
Write-Host 'NOTE: This verifier is NOT a WCAG audit or end-to-end browser test.'
