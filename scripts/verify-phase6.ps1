# Tourismo Phase 6 read-only verification (Windows PowerShell 5.1).
# Checks prior phases, stateless budgeting, and authenticated trip access rules.
# Never creates, changes or deletes a user's saved trip.
$ErrorActionPreference = 'Stop'
Write-Host 'Tourismo Phase 6 read-only verification'
$previous = Join-Path $PSScriptRoot 'verify-phase54.ps1'
& powershell -NoProfile -ExecutionPolicy Bypass -File $previous
if ($LASTEXITCODE -ne 0) { throw 'Phase 5.4 checks failed. Install and verify Phase 5.4 first.' }

$base = 'http://localhost:8000'
$draft = @{
    destination_slug = 'kandy'
    title = 'Phase 6 read-only budget check'
    adults = 2
    children_ages = @(8)
    currency = 'LKR'
    budget_limit_minor = 30000
    budget_flexible = $false
    itinerary = @(@{ day = 1; title = 'Public API test stop' })
    budget_items = @(
        @{ category = 'food'; description = 'Lunch'; day = 1; minimum_minor = 1000; expected_minor = 2000; maximum_minor = 4000 }
        @{ category = 'food'; description = 'Dinner'; day = 1; minimum_minor = 2000; expected_minor = 3000; maximum_minor = 6000 }
        @{ category = 'transport'; description = 'Taxi'; day = 2; minimum_minor = 5000; expected_minor = 8000; maximum_minor = 13000 }
        @{ category = 'misc'; description = 'Trip-wide'; minimum_minor = 100; expected_minor = 200; maximum_minor = 300 }
    )
}
$json = ConvertTo-Json -InputObject $draft -Depth 12 -Compress
$preview = Invoke-RestMethod -Uri "$base/api/v1/trips/preview" -Method POST -ContentType 'application/json' -Body $json -TimeoutSec 30
if ($preview.currency -ne 'LKR' -or $preview.minimum_minor -ne 8100 -or
    $preview.expected_minor -ne 13200 -or $preview.maximum_minor -ne 23300 -or
    $preview.per_traveler_expected_minor -ne 4400 -or $preview.unassigned.expected_minor -ne 200) {
    throw 'Phase 6 budget totals do not match the expected integer-cent calculation.'
}
if (@($preview.by_day).Count -ne 2 -or $preview.by_day[0].day -ne 1 -or
    $preview.by_day[0].expected_minor -ne 5000 -or
    $preview.by_day[1].day -ne 2 -or $preview.by_day[1].expected_minor -ne 8000) {
    throw 'Daily grouping is invalid.'
}
$food = @($preview.by_category | Where-Object { $_.category -eq 'food' })
if ($food.Count -ne 1 -or $food[0].expected_minor -ne 5000) {
    throw 'Category grouping is invalid.'
}

# Unauthorized access must not read, write or delete a private cloud trip.
$fakeId = '00000000-0000-0000-0000-000000000001'
foreach ($method in @('GET', 'PATCH', 'DELETE')) {
    $params = @{Uri="$base/api/v1/trips/$fakeId"; Method=$method; UseBasicParsing=$true; TimeoutSec=15}
    if ($method -eq 'PATCH') {
        $params['ContentType'] = 'application/json'
        $params['Body'] = '{"expected_version":1,"draft":{}}'
    }
    try {
        Invoke-WebRequest @params | Out-Null
        throw "Guest $method private trip unexpectedly succeeded."
    } catch [System.Net.WebException] {
        if ($null -eq $_.Exception.Response -or [int]$_.Exception.Response.StatusCode -ne 401) {
            throw "Expected HTTP 401 for guest $method; got $($_.Exception.Message)"
        }
    }
}
$revision = docker compose --env-file .env -f infra/compose.yaml exec -T db `
    psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
if ($LASTEXITCODE -ne 0 -or ($revision -join '').Trim() -ne '0015_location_links') {
    throw 'Unexpected database migration; Phase 6 should not require a new migration.'
}
Write-Host 'PASS: Day/category/per-traveler budget totals, guest privacy, migration 0015_location_links.'
Write-Host 'MANUAL: Save a trip, edit it from /saved, verify version increments and two-tab stale-save HTTP 409.'
Write-Host 'MANUAL: Check day assignments, estimate ranges, mobile expense editor, save as new copy, and confirmed deletion.'
