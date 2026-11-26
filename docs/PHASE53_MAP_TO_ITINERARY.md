# Tourismo Phase 5.3 — Map-Based Trip Planning

**Source-level release:** 23 November 2026
**Prerequisite:** Phase 5.2 Smart Nearby Discovery applied. Phase 5.2 local acceptance was not shown in conversation as of this release.
**Database migration:** None (remains `0015_location_links`).
**Status:** Implemented and backend-tested; full frontend build and local browser acceptance still required.

## User workflows

1. A guest visits `/map` or `/nearby`, selects a publicly mapped destination, attraction, or independently published service, and clicks **Add to trip**.
2. The action opens `/plan?add_place=<kind:uuid>`. Tourismo checks the stable reference against the public map API before adding a stop to Day 1. Reopening the same link does not duplicate that place on that day.
3. The guest may change **Day**, edit a **Note**, move a stop earlier/later within its day, remove stops, and select **All days** or one day for map display. Guests can still add ordinary text-only stops for activities without a mapped place.
4. The map displays the currently public pins in day sequence. Dashed lines are schematic point-to-point connections only; they are **not roads, verified routes, driving times, entrance directions or booking confirmation**. An optional outbound link hands off the destination coordinates to an external directions provider; availability and accuracy remain that provider's responsibility.
5. Guest itinerary changes remain in browser session storage. A signed-in tourist can **save a private snapshot**, using the existing authenticated and idempotent `POST /api/v1/trips` workflow. `/saved` displays that snapshot and provides a read-only itinerary map. Existing saved-trip records and ordinary manually typed stops remain valid.
6. If a previously public provider becomes archived, rejected, affected by expired license evidence, or unmapped, Tourismo **keeps the guest's note/title** but omits the public marker and provider link. A user's private trip does not grant access to hidden business information.

## API and data contracts

### `POST /api/v1/map/itinerary-places` (public, read-only)

Body: `{"place_ids":["destination:<uuid>","attraction:<uuid>","service:<uuid>"]}` with **1 to 90** canonical IDs. IDs are parsed strictly (type and hyphenated UUID). Any invalid ID → HTTP 422.

Response: array of matching, **currently public, coordinate-bearing** `MapPoint` records **in requested order**, without duplicates. Non-public/missing/unmapped records are omitted instead of returning placeholders or private metadata. Query batching uses at most three SQL statements by place kind, reusing `_public_query()` for services and editorial `sample`/`published` gates for destinations and attractions. All three categories require valid coordinates. Fictional demo providers are excluded.

### Trip itinerary `Stop` (backward-compatible)

Previously: `{day,title,note}`. Now additionally accepts an optional `place_id` referencing a public place as `kind:uuid`. The `place_id` is user-generated input for **private** drafts, not a public-data authorization capability. It cannot be a raw URL or an arbitrary string. No coordinate snapshots, business documents or provider contact details are inserted into trip JSONB.

`POST /api/v1/trips/preview` remains guest-accessible and performs budget calculation without a DB write. `POST /api/v1/trips` remains authenticated. `GET /api/v1/trips` and `GET /api/v1/trips/{id}` are owner-scoped. There is **no** cloud-trip overwrite/update/delete API in Phase 5.3; trip revisions and concurrency control remain Phase 6 work.

### Rate limits and permissions

The read-only place-resolution endpoint is covered by the existing per-process anonymous rate limiter. Production still requires a shared/edge rate limiter. Public result generation **requeries current publication state**, not stored stop metadata. The guest API has no access to unpublished listing revisions, draft-only POIs, private business documents, emails or provider profile data.

## Installation

Download the changes-only patch to your Windows Downloads folder, then from the Tourismo repository:

```powershell
cd D:\Tourismo\Tourismo
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase53_Map_To_Itinerary_Changes_Only.patch"
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Phase 5.3 patch conflicts. Stop. Do not force-apply.' }
git apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Phase 5.3 patch was not applied.' }
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase53.ps1
```

**Do not reapply Phase 5.1, delete database volumes, restore older source files, or replace the customized Compose file.** If `git apply --check` fails, share exact conflicting filenames; the user's local modifications should be merged using a targeted patch as in earlier phases.

## Acceptance checklist

- [ ] Phase 5.2 already applied and its verifier passes; `0015_location_links` remains Alembic head.
- [ ] `npm run build` and Docker image build succeed (not checked here due to unavailable npm registry).
- [ ] As a guest, open `/map`; **Add to trip** navigates to `/plan` and adds a new linked stop with a day and editable note.
- [ ] Open `/nearby`; select a mapped attraction/service; the same action works without login.
- [ ] Reopen the same URL on the same day; no duplicate; change the stop to another day and reorder within that day.
- [ ] A hand-entered stop still works, even without coordinates; multi-day list and map filters work on desktop and mobile.
- [ ] The map displays only visible public points; a removed/unpublished service reference is not visualized.
- [ ] Dashed lines are described as schematic; there are no invented road distances, road directions, prices or travel times.
- [ ] Anonymous trip save requires login; a signed-in user can create and re-open a private saved snapshot, with a single usable map preview.
- [ ] A second account cannot access the first user's saved trips or private details; no guest endpoint reveals private business documentation.
- [ ] Verify wheel zoom, arrow/reorder controls, and keyboard accessibility.

## Tests and known limits

Executed backend automated suite: `PYTHONPATH=. pytest -q` from `apps/api`: **173 passed, 5 skipped** before final documentary adjustments. New map reference tests cover invalid IDs, public visibility filters, verified badges, response ordering, preview compatibility and preservation of previously stored stops. Frontend TS/TSX syntax transpilation and UTF-8 guard pass. Full Vite build, PostgreSQL integration and real browser interactions must be confirmed locally.

Early catalog still has sparse sourced coordinates. A linked stop without coordinates remains a usable manual stop but cannot display a point. External navigation relies on an external service and its terms. The map displays point sequence only; route optimization, collaborative edits, pricing, drive times and revisions belong to later phases.
