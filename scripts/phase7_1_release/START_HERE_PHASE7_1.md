# Tourismo Phase 7.1 — Multiple Reviews, Auto-publication & Safe Photos

**Purpose:** Complete this revision **before** starting Phase 8 enquiries/quotations.

**Release format:** The included Python tool generates a real Git **changes-only patch against your local Phase 7 source**. A universal pre-generated diff cannot be verified because the original repository has local customizations and is not available for direct checkout here. This approach avoids guessing and lets `git apply --check` verify every actual source hunk.

This is a **changes-only, defensive source installer**, not a full replacement repository. It expects the **Phase 7 code** to exist in `D:\Tourismo\Tourismo`. It never touches your `infra/compose.yaml`, `.env`, custom maps, listing editors, location links, existing database data or earlier migrations.

## What changes

| Requirement | Phase 7.1 behaviour |
|---|---|
| Up to five reviews | Five **separate reviews per user per real published listing** (count includes hidden records, preventing cap evasion). User may edit their own review. |
| Automatic publication | Clean text is published after the configured **server-side moderation service** confirms it. Flagged text or moderation outage stays `pending` for admins. |
| Photos | Up to five photos on each review; JPEG, PNG or WebP; up to 2 MB input each. Re-encoded to sanitized JPEG (max 1280 px / max 1 MB stored each) and checked before storage. |
| Violating photos | Photos flagged by the moderation provider are **rejected** (HTTP 422). Image-check failures and missing credentials reject photo submissions (HTTP 503); they are never published unscanned. |
| Frontend preview | First 5 newest published reviews; **See more reviews** fetches 5 more per click. |
| Reputation fairness | Average rating is average of each reviewer's average, so one reviewer posting five times has the same *overall* weight as another reviewer posting once. |
| Review media privacy | Image URLs resolve only while the associated review is published **and** its listing is publicly eligible; no private image URLs or moderation notes are exposed. |

Moderation is probabilistic. Manual reporting, admin oversight, user appeals and appropriate privacy/CSAM controls are still needed for production. Existing provider replies remain moderated as in Phase 7; this change affects **customer reviews**, not provider replies.

## Requirements

- Windows PowerShell, Docker Compose and an existing working Phase 7 repository.
- PostgreSQL running at the **Phase 7** revision `0016_customer_reviews` before applying this update.
- Python 3 installed locally to run the installer, **or** Docker with `python:3.12-slim` (commands below).
- An OpenAI API key made available to the **API container only** for automatic text and image moderation. Never expose the key in Vite/frontend variables or Git.
- Explicit privacy notice/consent appropriate for transmitting review text and photos to the configured moderation provider. Don't enable public photo submissions in production without policies and moderation compliance review.

## 1. Back up database and source first

```powershell
cd D:\Tourismo\Tourismo
git status --short
$dbContainer = docker compose --env-file .env -f infra/compose.yaml ps -q db
if (-not $dbContainer) { throw 'PostgreSQL container is not running' }
$backup = "tourismo-before-phase7-1-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
docker compose --env-file .env -f infra/compose.yaml exec -T db `
  pg_dump -U tourismo -d tourismo -Fc -f /tmp/tourismo-before-phase7-1.dump
if ($LASTEXITCODE -ne 0) { throw 'DB backup failed' }
docker cp "${dbContainer}:/tmp/tourismo-before-phase7-1.dump" ".\$backup"
if ($LASTEXITCODE -ne 0) { throw 'DB backup export failed' }
Write-Host "Backup saved as $backup"
```

**Do not** run `docker compose down -v`, drop the database or replay Phase 7 migrations. This installer only creates the new additive migration; Docker's existing startup may run the Alembic upgrade.

## 2. Add the patch generator, then dry-run

**Option A — `.patch` first (recommended if you prefer Git patches):** Download `Tourismo_Phase7_1_Review_Enhancements_Bootstrap.patch` into Downloads and run:

```powershell
cd D:\Tourismo\Tourismo
$bootstrap = "$env:USERPROFILE\Downloads\Tourismo_Phase7_1_Review_Enhancements_Bootstrap.patch"
git apply --check $bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap patch conflict; stop' }
git apply $bootstrap
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap patch failed; stop' }
$pack = Join-Path (Get-Location) 'scripts\phase7_1_release'
```

**Important:** The bootstrap patch adds the Phase 7.1 update files and patch generator to the repository; the **actual existing-source modifications** are produced in step 3 as a second, exact-source Git patch. It does *not* activate the new review behavior by itself.

**Option B — ZIP package (same generator, without adding installer files to Git):** Extract `Tourismo_Phase7_1_Review_Enhancements.zip` outside the repository, for example into `Downloads\Tourismo_Phase7_1_Review_Enhancements`; point `$pack` at that extracted directory. **Use only one option; don't apply both bootstrap patch and ZIP.** The installer assumes the working directory is the repository root.

```powershell
cd D:\Tourismo\Tourismo
# Only for ZIP option: $pack = "$env:USERPROFILE\Downloads\Tourismo_Phase7_1_Review_Enhancements"
py -3 "$pack\tools\apply_phase7_1.py" --check
```

If Python is only available through Docker:

```powershell
cd D:\Tourismo\Tourismo
# $pack was set in Option A or B above
docker run --rm `
  -v "${PWD}:/work" `
  -v "${pack}:/release:ro" `
  -w /work python:3.12-slim python /release/tools/apply_phase7_1.py --check
```

The installer is conservative about source anchors. It generates an updated `CustomerReviews.tsx`, so compare and merge any personal UI customizations before applying. The preflight **refuses** to proceed if it detects a conflicting Phase 8 `0017_service_enquiries.py` migration, a previously applied Phase 7.1 migration, missing Phase 7 routes, or unrecognized source anchors. Compare changes to customized routes/UI manually: the new API review functions and customer-review component will replace their Phase 7 equivalents.

## 3. Generate and apply the EXACT changes-only Git patch (recommended)

After a successful dry-run and verified backup, create the patch using the current Phase 7 source tree:

```powershell
cd D:\Tourismo\Tourismo
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase7_1_Reviews_Changes_Only.patch"
py -3 "$pack\tools\apply_phase7_1.py" --export-patch $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch generation failed; do not continue' }
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch conflict: do not apply or force changes' }
git apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch apply failed; stop and investigate' }
git diff --stat
```

The `--export-patch` mode **does not write project source**; only the resulting patch file is created. It captures the exact Phase 7 files on your machine, meaning `git apply` checks compatibility against the same files. If the working tree changes between patch generation and application, rerun the preflight and export; never force a rejected patch.

For Docker-only environments, replace the `py -3 ... --export-patch` line with:

```powershell
docker run --rm -v "${PWD}:/work" -v "${pack}:/release:ro" `
  -v "$env:USERPROFILE\Downloads:/out" -w /work `
  python:3.12-slim python /release/tools/apply_phase7_1.py `
  --export-patch /out/Tourismo_Phase7_1_Reviews_Changes_Only.patch
```

**Alternative:** `py -3 "$pack\tools\apply_phase7_1.py" --apply` directly writes source files after creating timestamped `.phase7_1_backup` copies. Prefer the Git patch workflow; do **not** run both methods for the same update. Do not commit backup files or secrets.


## 4. Configure moderation safely

`apps/api/requirements.txt` gets Pillow dependency. Add `OPENAI_API_KEY` to the API service's **server-side** environment using the existing secret-management mechanism; avoid editing the customized Compose file blindly. Depending on your Compose setup, a local `.env` file **is not automatically forwarded** to containers unless the Compose service explicitly references it.

- With a working API key: clean text posts automatically, flagged text stays pending, flagged photos are rejected.
- Without a key: **text-only** posts are pending for admin approval; **photo** posts are rejected with HTTP 503. Nothing is incorrectly auto-published.
- If the API key or moderation endpoint has an outage: same fail-closed behaviour.

The implementation uses the currently documented `/v1/moderations` `omni-moderation-latest` multimodal text/image API. Server must have outbound HTTPS; all moderation calls are time-bounded.

**Upload infrastructure:** Five 2 MB files encoded in JSON can exceed 13 MB on the wire. Ensure the frontend gateway, ingress, reverse proxy and API body limits allow at least 16 MB for this review endpoint before enabling maximum-size uploads. Requests still need per-user/IP rate limits and storage quotas; the application should not accept arbitrary unlimited photo uploads. The current implementation stores compressed JPEG data in PostgreSQL for pilot use; private object storage is preferable at scale.

## 5. Rebuild and run migration

```powershell
docker compose --env-file .env -f infra/compose.yaml up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Docker rebuild failed' }
docker compose --env-file .env -f infra/compose.yaml ps
docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c 'SELECT version_num FROM public.alembic_version;'
```

**Expected revision:** `0017_review_media`.

If your application does not automatically apply migrations on container startup, run `alembic upgrade head` using the existing application's configured migration command. Confirm the expected revision before continuing.

## 6. Quality checks

```powershell
docker compose --env-file .env -f infra/compose.yaml exec -T app `
  python -m pytest -q apps/api/tests/test_phase7_customer_reviews.py apps/api/tests/test_phase71_review_policy.py
```

**Important:** The `app` container's working directory may already be `apps/api`; adjust the file paths or service name according to your Compose definition. Also run the full existing test suite and frontend TypeScript build; this update has not been compiled against your exact local repository.

Browser acceptance checklist:

1. Guest sees 5 published reviews and **See more reviews** loads 5 per click.
2. Signed-in, profile-complete tourist creates 1 through 5 reviews on the same real listing.
3. The sixth review returns 409 and the frontend prompts the user to edit an existing review.
4. Editing someone else's review returns 404; an author can edit their own existing review.
5. A clean text review is published automatically **only when moderation is configured and confirms it**.
6. A flagged text review remains pending and not public until independently reviewed by admin.
7. Upload 1 to 5 safe photos; check the gallery and resized/metadata-stripped JPEGs.
8. Upload a prohibited or invalid photo; confirm 422 and no record/photos created.
9. Disable moderation temporarily; confirm photos return 503 and clean text does not auto-publish unchecked.
10. Hide a published review as admin; confirm associated photo URLs return 404.
11. Confirm business self-review restrictions, provider reply moderation, report queue, saved trips and map unchanged.
12. Confirm the rating average gives each unique reviewer equal total weight, not five times the weight.

## Phase 8 migration compatibility

The Phase 8 pack that was previously prepared used revision `0017_service_enquiries` with Phase 7 as its parent. **Do not apply that old Phase 8 migration after this upgrade.** It must first be rebased to a new revision (for example `0018_service_enquiries` with `down_revision='0017_review_media'`) and its verifier updated. Phase 8 can resume only after Phase 7.1 acceptance.

## Limitations / honest release status

This release pack's Python files, media safety behavior and installer were syntax-checked and dry-run against a simulated Phase 7 source structure. The exact current local Tourismo repository and live database cannot be accessed here; **no claim is made that this release has passed Docker, Alembic, React, authentication or browser integration tests on your computer**. The patch exporter was tested in a simulated Phase 7 repository: bootstrap application, dry-run, patch creation, `git apply --check`, application and Python syntax validation passed. Local image tests confirmed 5-image validation, 6th-image rejection, sanitized JPEG conversion, flagged-image rejection and fail-closed moderation. The actual source patch must be produced locally using the included exporter.

Photo content is transmitted to an external moderation provider and stored as sanitized JPEG **inside PostgreSQL**. This is a practical local/pilot solution, **not an economical storage strategy at scale**; switch to private object storage and asynchronous scanning before public launch. Model moderation has blind spots (including text in images and certain child-safety categories); use specialized safety controls and human escalation for production, and do not process or forward known illegal child-abuse material to a general moderation model.
