# Optional convenience entry point; use the same verified Windows PowerShell 5.1 parser.
$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot 'verify-phase51.ps1'
& powershell -NoProfile -ExecutionPolicy Bypass -File $path
if ($LASTEXITCODE -ne 0) { throw 'Phase 5.1 location-link verification failed.' }
