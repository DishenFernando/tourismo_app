# TOURISMO — Phase 9A Installation (after Phase 8)

**Next milestone:** Content quality, English/Sinhala/Tamil navigation preview, accessibility and SEO metadata foundation.
**No new database migration:** current revision stays `0018_service_enquiries`.
**Not yet included:** fully translated destination articles, editorial CMS translation publication, native language/legal signoff, SEO SSR and complete WCAG certification. These are Phase 9B follow-ups.

## What you receive

- `Tourismo_Phase9A_Bootstrap.patch`: installs the generator and its assets under `scripts/phase9_release/` without replacing your source.
- `Tourismo_Phase9A_Release_Kit.zip`: alternative package containing the same generator and assets.
- `Tourismo_Phase9A_Changes_Only.patch`: **generated on your computer** from your exact source. Do not apply a patch from a synthetic repository.

Choose **one** installation route: bootstrap patch or extracted ZIP; do not install both over the same paths. The actual Phase 9A feature update is always the exported changes-only patch.

## 1. Verify Phase 8 first

```powershell
cd D:\Tourismo\Tourismo
git status --short
$rev = docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c "SELECT version_num FROM public.alembic_version;"
if ($LASTEXITCODE -ne 0 -or ($rev -join '').Trim() -ne '0018_service_enquiries') {
    throw "Expected Phase 8 database revision 0018_service_enquiries; got $rev"
}
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase8.ps1
```

If Phase 8's migration, private enquiry isolation, or review media checks are not yet passing, fix those before going further. `verify-phase8.ps1` is not a substitute for logged-in tourist/vendor browser testing.

## 2. Back up PostgreSQL, preserve local source

Phase 9A has no new DB schema, but always back up before deploying a new image:

```powershell
$dbContainer = docker compose --env-file .env -f infra/compose.yaml ps -q db
if (-not $dbContainer) { throw 'Postgres container not found' }
$backup = "tourismo-before-phase9a-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
docker compose --env-file .env -f infra/compose.yaml exec -T db `
  pg_dump -U tourismo -d tourismo -Fc -f /tmp/tourismo-before-phase9a.dump
if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed' }
docker cp "${dbContainer}:/tmp/tourismo-before-phase9a.dump" ".\$backup"
if ($LASTEXITCODE -ne 0) { throw 'Backup export failed' }
Write-Host "Database backup: $backup"
```

Commit a source checkpoint if appropriate, but do not commit `.env`, private uploads, credentials or backups. Never use `docker compose down -v`.

## 3. Install the generator (recommended bootstrap approach)

Save `Tourismo_Phase9A_Bootstrap.patch` in Windows Downloads.

```powershell
$bootstrap = "$env:USERPROFILE\Downloads\Tourismo_Phase9A_Bootstrap.patch"
git apply --check $bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap conflict: stop' }
git apply $bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap application failed: stop' }
$generator = ".\scripts\phase9_release\generate_phase9_patch.py"
```

**ZIP alternative:** Extract `Tourismo_Phase9A_Release_Kit.zip` to Downloads, then set `$generator` to the extracted `generate_phase9_patch.py`. Do not apply bootstrap if you use the ZIP alternative.

## 4. Generate a source-compatible Phase 9A patch

```powershell
py -3 $generator --root . --check
if ($LASTEXITCODE -ne 0) { throw 'Phase 9A compatibility check failed' }

$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase9A_Changes_Only.patch"
py -3 $generator --root . --output $patch
if ($LASTEXITCODE -ne 0) { throw 'Phase 9A patch generation failed' }

git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Generated patch conflict: stop' }
git apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed: stop' }
```

The generator **never edits existing application source directly**; it requires known App/Header anchors, Phase 7.1/Phase 8 migrations and Phase 8 enquiries code. It refuses to overwrite Phase 9A files or force a mismatch. A dry run does not modify source.

## 5. Rebuild and verify

```powershell
docker compose --env-file .env -f infra/compose.yaml up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed' }

docker compose --env-file .env -f infra/compose.yaml ps
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase9.ps1
```

There is **no Phase 9A Alembic migration**. `0018_service_enquiries` remains the expected version.

## 6. Browser acceptance

1. Open `/` and use Tab. The **Skip to main content** control should become visible and focus the main route container.
2. Choose English, Sinhala, Tamil in the language dropdown. The nav labels change; refresh to verify persistence.
3. Verify the visible notice explains that only navigation labels are in preview; destination content is still English.
4. Open `/accessibility`. Confirm keyboard help, current limitations, and return navigation.
5. Navigate `/discover`, `/destinations/:slug`, `/listings/:slug`, `/enquiries` and `/admin`. Document titles should change; private routes must remain auth-protected.
6. Check private metadata, public canonical link on HTTPS and no canonical link on localhost. These are client-side enhancements, **not** a substitute for real server-side SEO.
7. Check responsive layout at 320, 375 and 768 px; no horizontal overflow from the language toolbar.
8. Regression: Phase 7.1 review/5-photo moderation, Phase 8 tourist↔vendor messages, maps, planner, vendor admin and role restrictions.
9. Screen-reader and native-language review must still be completed before marking the whole phase accepted.

## Source QA

- Python generator syntax and defensive precondition checks tested.
- Synthetic Git patch exported and `git apply --check` tested on a representative Phase 8-like checkout.
- TSX files parsed with TypeScript transpiler; this does **not** run your full `npm run build`.
- No actual Docker/frontend/PostgreSQL/Clerk/browser acceptance has been performed against your Windows checkout.

## Phase 9B after 9A acceptance

Implement actual content revision workflow for native-reviewed Sinhala/Tamil guide summaries and details, search parity, SEO/prerendering, structured source provenance and full accessibility sweep. Do not fabricate translations or metadata for unreviewed content.
