# Tourismo Phase 7 read-only checks for Windows PowerShell 5.1.
# Does not create a review, report, provider response, or moderation decision.
$ErrorActionPreference = 'Stop'
$base = 'http://localhost:8000'
Write-Host 'Tourismo Phase 7: Reviews, Ratings & Trust (read-only verification)'

# Container and database health; no reset or migration is performed by this script.
docker compose --env-file .env -f infra/compose.yaml ps
if ($LASTEXITCODE -ne 0) { throw 'Unable to list Docker containers.' }
$revision = docker compose --env-file .env -f infra/compose.yaml exec -T db `
    psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
if ($LASTEXITCODE -ne 0 -or ($revision -join '').Trim() -ne '0016_customer_reviews') {
    throw "Expected database revision 0016_customer_reviews, received: $revision"
}
$ready = Invoke-RestMethod -Uri "$base/api/v1/health/ready" -TimeoutSec 20
if ($ready.status -ne 'ok') { throw 'API readiness check failed.' }

function Assert-GuestUnauthorized([string]$path, [string]$method, [string]$payload='') {
    $request = @{Uri="$base$path";Method=$method;UseBasicParsing=$true;TimeoutSec=15}
    if ($method -eq 'POST') { $request['ContentType']='application/json'; $request['Body']=$payload }
    try {
        Invoke-WebRequest @request | Out-Null
        throw "SECURITY FAIL: guest $method unexpectedly succeeded on $path"
    } catch [System.Net.WebException] {
        if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 401) {
            throw "Expected 401 for guest $method $path: $($_.Exception.Message)"
        }
    }
}
$fake = '00000000-0000-0000-0000-000000000001'
Assert-GuestUnauthorized '/api/v1/reviews/listings/example/mine' 'GET'
Assert-GuestUnauthorized '/api/v1/reviews/listings/example' 'POST' '{"rating":5,"title":"Test feedback","body":"This is a sample comment for privacy testing."}'
Assert-GuestUnauthorized "/api/v1/reviews/$fake/reports" 'POST' '{"reason":"spam","explanation":"This is a sample complaint for privacy testing."}'
Assert-GuestUnauthorized '/api/v1/admin/customer-reviews' 'GET'
Assert-GuestUnauthorized '/api/v1/admin/customer-reviews/replies' 'GET'
Assert-GuestUnauthorized '/api/v1/admin/customer-reviews/reports' 'GET'
Assert-GuestUnauthorized "/api/v1/vendor/organizations/$fake/customer-reviews" 'GET'
Assert-GuestUnauthorized "/api/v1/vendor/organizations/$fake/customer-reviews/$fake/response" 'POST' '{"body":"Thank you for sharing this information."}'

# Optional public contract: only test a real, independently published listing if one exists.
$directory = Invoke-RestMethod -Uri "$base/api/v1/listings?limit=1" -TimeoutSec 30
$items = @($directory | Where-Object { $null -ne $_ -and $null -ne $_.slug })
if ($items.Count -gt 0) {
    $slug = [Uri]::EscapeDataString([string]$items[0].slug)
    $reviews = Invoke-RestMethod -Uri "$base/api/v1/reviews/listings/$slug" -TimeoutSec 30
    if ($reviews.count -lt 0 -or ($null -eq $reviews.visit_verified) -or $reviews.visit_verified -ne $false) {
        throw 'Public review summary contract is invalid or claims a verified visit.'
    }
    foreach ($review in $reviews.reviews) {
        if ($review.PSObject.Properties.Name -contains 'author_id' -or
            $review.PSObject.Properties.Name -contains 'moderation_note' -or
            $review.PSObject.Properties.Name -contains 'email') {
            throw 'Public review endpoint exposed private identity or moderation information.'
        }
    }
    Write-Host "PASS: Public review summary checked for listing $slug."
} else {
    Write-Host 'INFO: No public listings available for review-summary inspection; auth checks still passed.'
}
Write-Host 'PASS: API ready, migration 0016_customer_reviews, guest access controls, and public review privacy.'
Write-Host 'MANUAL: Complete profile -> submit feedback -> admin approve -> rating appears on service page.'
Write-Host 'MANUAL: Owner/member cannot review own listing; vendor response requires approval; report/resolve works.'
Write-Host 'MANUAL: Check historical Phase 6 trip save/edit, map interactions, and mobile layout.'
