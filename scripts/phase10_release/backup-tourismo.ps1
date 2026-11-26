<#
Tourismo Phase 10A: non-destructive local backup of PostgreSQL and private vendor documents.
Windows PowerShell 5.1-compatible. Does NOT restore, prune, rotate, reset or delete Docker volumes.
Sensitive backups must be encrypted/offsite under an approved retention policy.
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = '.',
    [string]$BackupRoot = (Join-Path $HOME 'TourismoBackups')
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$project = (Resolve-Path $ProjectRoot).Path.TrimEnd('\')
$targetRoot = [IO.Path]::GetFullPath($BackupRoot).TrimEnd('\')
if ($targetRoot.StartsWith($project + '\', [StringComparison]::OrdinalIgnoreCase) -or
    $targetRoot.Equals($project, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to put sensitive backups inside the Git repository. Set -BackupRoot outside the project.'
}
if (-not (Test-Path (Join-Path $project 'infra\compose.yaml'))) {
    throw 'Could not locate infra/compose.yaml'
}
if (-not (Test-Path (Join-Path $project '.env'))) {
    throw 'Could not find private .env. Stop instead of guessing credentials.'
}
Push-Location $project
try {
    $compose = @('compose', '--env-file', '.env', '-f', 'infra/compose.yaml')
    $dbContainer = (& docker @compose ps -q db | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $dbContainer) { throw 'DB container is not running' }
    $appContainer = (& docker @compose ps -q app | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $appContainer) { throw 'Application container is not running' }

    $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $folder = Join-Path $targetRoot "tourismo-$stamp"
    if (Test-Path $folder) { throw 'Backup folder already exists; refusing to overwrite' }
    New-Item -Path $folder -ItemType Directory -Force | Out-Null
    $dumpInContainer = "/tmp/tourismo-$stamp.dump"
    $dbFile = Join-Path $folder 'tourismo-postgres.dump'
    $docsDir = Join-Path $folder 'private_vendor_documents'
    $success = $false
    try {
        & docker @compose exec -T db pg_dump -U tourismo -d tourismo -Fc -f $dumpInContainer
        if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL pg_dump failed' }
        & docker @compose exec -T db pg_restore -l $dumpInContainer *> $null
        if ($LASTEXITCODE -ne 0) { throw 'pg_restore could not list backup contents' }
        & docker cp "${dbContainer}:$dumpInContainer" $dbFile
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dbFile)) { throw 'Backup export failed' }
        if ((Get-Item $dbFile).Length -lt 100) { throw 'Exported database dump is unexpectedly small' }

        # Includes unreviewed private evidence. Treat this folder as sensitive.
        New-Item -Path $docsDir -ItemType Directory | Out-Null
        & docker cp "${appContainer}:/app/private_vendor_documents/." $docsDir
        if ($LASTEXITCODE -ne 0) { throw 'Private vendor document backup failed' }

        $sha = (Get-FileHash -Path $dbFile -Algorithm SHA256).Hash
        @(
            'Tourismo backup manifest (UTC)'
            "Backup timestamp: $stamp"
            'Database: PostgreSQL pg_dump custom format'
            "Database SHA256: $sha"
            'Documents: private_vendor_documents (unencrypted local snapshot)'
            'Status: database archive listing verified; live restore NOT tested'
            'Required next: encrypt, move offsite, and perform an isolated restore rehearsal'
            'Does NOT include environment secrets, DNS, certificates, mail/push credentials or external storage.'
        ) | Set-Content -Path (Join-Path $folder 'MANIFEST.txt') -Encoding UTF8
        $success = $true
        Write-Host "Backup created successfully: $folder"
        Write-Warning 'Backup contains private information. Restrict permissions, encrypt, and move offsite.'
    } finally {
        & docker @compose exec -T db rm -f $dumpInContainer 2>$null | Out-Null
        if (-not $success) {
            Write-Warning "Backup is incomplete: $folder. Do not use it as a recovery point."
        }
    }
} finally { Pop-Location }
