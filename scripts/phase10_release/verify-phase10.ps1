<# Phase 10A read-only deployment smoke check. Does not send notifications or create data. #>
[CmdletBinding()]
param(
    [string]$ProjectRoot = '.',
    [string]$BaseUrl = 'http://localhost:8000',
    [string]$ExpectedRevision = '0019_notifications_trust'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$project = (Resolve-Path $ProjectRoot).Path
Push-Location $project
try {
    $compose = @('compose', '--env-file', '.env', '-f', 'infra/compose.yaml')
    function CheckEndpoint([string]$url, [int]$expectedStatus) {
        try {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 12 -ErrorAction Stop
            $status = [int]$response.StatusCode
        } catch [System.Net.WebException] {
            if ($_.Exception.Response) { $status = [int]$_.Exception.Response.StatusCode } else { throw }
        }
        if ($status -ne $expectedStatus) { throw "Unexpected HTTP $status, expected $expectedStatus, for $url" }
        Write-Host "PASS HTTP $status $url"
    }
    CheckEndpoint "$BaseUrl/api/v1/health/live" 200
    CheckEndpoint "$BaseUrl/api/v1/health/ready" 200

    $rev = (& docker @compose exec -T db psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;' | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Could not read Alembic revision' }
    if ($rev -ne $ExpectedRevision) { throw "Alembic revision mismatch. Expected $ExpectedRevision, found $rev" }
    Write-Host "PASS migration $rev"

    # In-app notification endpoint must not expose personal data to a guest.
    $privateEndpoint = "$BaseUrl/api/v1/notifications"
    $guestStatus = 0
    try {
        $r = Invoke-WebRequest -Uri $privateEndpoint -UseBasicParsing -TimeoutSec 12 -ErrorAction Stop
        $guestStatus = [int]$r.StatusCode
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) { $guestStatus = [int]$_.Exception.Response.StatusCode } else { throw }
    }
    if ($guestStatus -notin @(401,403)) { throw "Notification privacy check failed: guest received HTTP $guestStatus" }
    Write-Host "PASS notification inbox denies anonymous requests ($guestStatus)"
    Write-Host 'PASS Phase 10A read-only smoke checks. Manual production release gates still required.'
} finally { Pop-Location }
