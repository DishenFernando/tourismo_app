# Extended Tourismo verification: original checks + full frontend UTF-8 audit.
# Requires Docker Desktop. Works in Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path
if (-not (Test-Path '.\apps\web\package.json')) {
    throw 'Open the Tourismo project root before running this verification.'
}
Write-Host 'Step 1: Existing Tourismo Pre-Phase-5 verification' -ForegroundColor Cyan
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\verify-pre-phase5.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Existing verification failed.' }
Write-Host 'Step 2: UTF-8 source and frontend guard' -ForegroundColor Cyan
$mount = 'type=bind,source=' + $root + ',target=/project'
& docker run --rm --mount $mount -w /project python:3.12-slim python scripts/repair-tourismo-text.py --check
if ($LASTEXITCODE -ne 0) { throw 'UTF-8 check failed: run the repair command in the installation guide.' }
& docker run --rm --mount $mount -w /project/apps/web node:22-alpine node scripts/check-encoding.mjs
if ($LASTEXITCODE -ne 0) { throw 'Frontend UTF-8 guard failed.' }
Write-Host 'PASS: Project APIs, database migration, and frontend UTF-8 source files verified.' -ForegroundColor Green
