# TOURISMO — Phase 8 Installation (AFTER Phase 7.1)

**Use with:** Tourismo Phase 7.1, whose latest Alembic revision is `0017_review_media`.

**Purpose:** Introduce authenticated tourist↔vendor enquiry threads while retaining the new five-reviews/five-photos review functionality and preventing an Alembic branching conflict.

**Release contents:**

- `Tourismo_Phase8_After_Phase71_Bootstrap.patch` — installs this rebase generator and guide into `scripts/phase8_compat/` and `docs/` (no existing app source files are overwritten).
- `phase8_rebase.py` — standalone alternative to installing the bootstrap patch.
- `START_HERE_PHASE8_AFTER_PHASE71.md` — this guide.

**Also required:** `Tourismo_Phase8_Enquiries_Changes_Only.patch`, the original Phase 8 release from your Tourismo release library. **Do NOT apply the original Phase 8 patch directly**: its `0017_service_enquiries` migration conflicts with the previously applied `0017_review_media` migration. Download that patch to your Windows `Downloads` folder first.

## Phase 7.1 acceptance gate

Before Phase 8, the `PAGE_SIZE` TypeScript error in `apps/web/src/features/CustomerReviews.tsx` must be fixed; the Phase 7.1 Docker build must succeed, with `0017_review_media` as the actual database revision.

```powershell
cd D:\Tourismo\Tourismo
# Only remove PAGE_SIZE if it is genuinely unused; see the earlier correction.
docker compose --env-file .env -f infra/compose.yaml up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Phase 7.1 Docker build is not passing' }
$revision = docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
if ($LASTEXITCODE -ne 0 -or ($revision -join '').Trim() -ne '0017_review_media') { throw "Expected 0017_review_media; got $revision" }
```

In the browser, verify 5 reviews per author/listing; auto-publication only after moderation; max five safe photos; initial five reviews with See more; report/hidden records and vendor restrictions. A green migration number by itself does **not** prove moderation is configured or photo uploads work.

## Back up your database

```powershell
cd D:\Tourismo\Tourismo
$dbContainer = docker compose --env-file .env -f infra/compose.yaml ps -q db
if (-not $dbContainer) { throw 'PostgreSQL container is not running' }
$backup = "tourismo-before-phase8-after71-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
docker compose --env-file .env -f infra/compose.yaml exec -T db `
  pg_dump -U tourismo -d tourismo -Fc -f /tmp/tourismo-before-phase8.dump
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
docker cp "${dbContainer}:/tmp/tourismo-before-phase8.dump" ".\$backup"
if ($LASTEXITCODE -ne 0) { throw 'Database backup export failed' }
Write-Host "Backup saved: $backup"
```

For additional protection, commit a Git checkpoint of your verified Phase 7.1 source before proceeding; **do not commit `.env` or API keys**.

## Install the bootstrap (one-time)

Place `Tourismo_Phase8_After_Phase71_Bootstrap.patch` in Downloads.

```powershell
$bootstrap = "$env:USERPROFILE\Downloads\Tourismo_Phase8_After_Phase71_Bootstrap.patch"
git apply --check $bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Phase 8 bootstrap conflict: STOP' }
git apply $bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Phase 8 bootstrap failed: STOP' }
```

Alternative: extract `Tourismo_Phase8_After_Phase71_Compatibility_Kit.zip` and use the Python script directly; do **not** apply both bootstrap and ZIP files over the same paths.

## Generate an exact changes-only Phase 8 patch

The generator reads the original Phase 8 source patch and your **current** local source files. It verifies the Phase 7.1 migration exists, transplants the Phase 8 changes only when old-code context matches, and emits a new patch. It makes **no edits to the application repository**.

```powershell
$oldPatch = "$env:USERPROFILE\Downloads\Tourismo_Phase8_Enquiries_Changes_Only.patch"
$newPatch = "$env:USERPROFILE\Downloads\Tourismo_Phase8_After_Phase71_Changes_Only.patch"
$generator = ".\scripts\phase8_compat\phase8_rebase.py"

py -3 $generator --root . --source $oldPatch --output $newPatch
if ($LASTEXITCODE -ne 0) { throw 'Rebase failed: STOP. Share the exact failure details.' }

git apply --check $newPatch
if ($LASTEXITCODE -ne 0) { throw 'Patch conflict: STOP. Do not use --reject or force flags.' }
git apply $newPatch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed: STOP.' }
```

The new patch renumbers the Phase 8 Alembic migration to:

```python
revision = '0018_service_enquiries'
down_revision = '0017_review_media'
```

The generator also updates the Phase 8 verifier and release documents to expect the new revision. Source differences it cannot match **stop the process** instead of silently overwriting your custom changes.

## Rebuild and test

```powershell
docker compose --env-file .env -f infra/compose.yaml up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Docker rebuild failed: inspect build output' }

docker compose --env-file .env -f infra/compose.yaml ps
$revision = docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
if ($LASTEXITCODE -ne 0 -or ($revision -join '').Trim() -ne '0018_service_enquiries') { throw "Unexpected revision: $revision" }

powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase8.ps1
```

Run the full backend suite and inspect browser console/network for errors as part of acceptance. The read-only verifier does not test actual Clerk accounts, vendor membership, user isolation or browser UI.

## Browser acceptance checklist

1. Guest can browse real listings but cannot submit or read an enquiry. Demo listings never show enquiry forms.
2. Signed-in tourist with a completed profile sends a new enquiry from a published real service listing.
3. Tourist sees thread in `/enquiries`; a different account cannot read it.
4. Vendor **owner/manager of the same organization** responds via `/vendor/enquiries`; unrelated vendors and staff members cannot read it.
5. Traveler sees reply; either side can follow up; withdrawing or closing blocks new messages.
6. Participant can report a thread; an admin sees it in `/admin/enquiry-reports` and can make a recorded decision.
7. Confirm original Phase 7.1 reviews still work: five-review preview + See more, photo visibility, moderation fallbacks, existing saved trips/maps/budgets.
8. Confirm server logs, browser errors and unauthorized-access responses.

## Important boundaries

- This release provides **in-app message threads**, not real reservations, payment processing or booking confirmations.
- Indicative quotes can be exchanged as message text; structured line-item quotations and inventory integration are *not* part of the earlier Phase 8 release.
- Phase 8 does **not** currently scan user-to-vendor message text for violations on submission. Use reports and admin moderation; implement additional policy controls before a public launch.
- Do not send IDs, bank/payment card details or other sensitive documents through conversations.
- No `.env`, Docker Compose or customer review source files are replaced by the bootstrap. The feature patch changes only the explicit 17 files in the original Phase 8 release.
- **Never run** `docker compose down -v`; do not use an Alembic downgrade that drops conversation history as routine rollback.

**Verification status:** Rebase tool was validated on a synthetic Git repository with Phase 7.1-style overlapping changes and `git apply --check`. It has **not** been tested against your actual Windows repository or Docker stack. If a hunk fails matching, STOP and share the message for a targeted fix.
