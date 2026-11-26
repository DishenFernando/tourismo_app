# Windows PowerShell 5.1 / 7 wrapper for the Tourismo UTF-8 repair.
# Run without -Fix to inspect; run with -Fix to repair and create backups.
param([switch]$Fix)
$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path
if (-not (Test-Path '.\apps\web\package.json')) {
    throw 'Please run from the Tourismo project root.'
}
$mode = if ($Fix) { '--fix' } else { '--check' }
$mount = 'type=bind,source=' + $root + ',target=/project'
& docker run --rm --mount $mount -w /project python:3.12-slim python scripts/repair-tourismo-text.py $mode
if ($LASTEXITCODE -ne 0) { throw 'Tourismo UTF-8 audit reported unresolved issues. See the output above.' }
Write-Host 'Tourismo encoding audit completed.' -ForegroundColor Green
