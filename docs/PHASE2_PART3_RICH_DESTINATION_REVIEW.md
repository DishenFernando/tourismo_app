# Tourismo Phase 2.3 — Rich destination content, galleries and editorial review

## Prerequisite

Apply this update **after Phase 2.2** (`0004_catalog_admin_media`). Existing users, role grants, destinations, profiles, trips and Docker environment are preserved.

## Added

1. **Destination photo gallery**: `GET /api/v1/destinations/{slug}/photos` returns every approved destination photo with creator, original Wikimedia file page and license attribution. Clicking a thumbnail changes the large image. No photos are invented or duplicated by this update. Admins can add more correctly sourced Commons photos with the existing photo form.
2. **Map-ready POI reference points**: optional `latitude`, `longitude` fields for attractions, stored with the existing PostGIS geography `location`. Public attraction cards link to the exact available point in OpenStreetMap; they explicitly warn that heritage-property coordinates are not entrances or routes. Editor POI creation accepts both coordinates only together and requires an HTTPS source. Most POIs are intentionally unlocated until verified.
3. **UNESCO-sourced reference points**: migration `0005_rich_destination_review` adds official UNESCO heritage-property coordinates for Galle, Kandy, Anuradhapura and Sigiriya. It also adds the source-linked **sample** guide and POI for Sigiriya without overwriting existing human-edited records.
4. **Editorial queue**: editors can submit sourced draft guides and POIs for admin review. Admins can inspect the queue, approve submitted guides (including Sinhala and Tamil when the destination is already published), approve sourced POIs via the established endpoint, or return submissions to draft with a required reason. Actions are written to the existing audit table. Existing direct admin publish actions are intentionally retained for backward compatibility.

## Editorial state flow

- Edit or create → `draft` (not visible to guests)
- Submit → `submitted` (admin review queue only, never public)
- Admin approves → `published` (public)
- Admin requests changes → `draft` with reason recorded in `audit_events`
- Original `sample` records remain visible with the existing **editorial sample** warning and may be edited or reviewed by staff.

Only authenticated accounts with a *database-granted* `editor` or `admin` role can submit; only the `admin` role can approve or request changes. Public sign-ups cannot self-assign privileged roles.

## New/updated API endpoints

- `GET /api/v1/destinations/{slug}/photos` — public gallery
- `GET /api/v1/destinations/{slug}/pois` — now includes nullable latitude/longitude
- `POST /api/v1/admin/destinations/{slug}/pois` — now accepts optional latitude/longitude, verified by source
- `GET /api/v1/admin/review-queue` — admin only
- `POST /api/v1/admin/destinations/{slug}/guide/submit?locale=en` — editor/admin
- `POST /api/v1/admin/destinations/{slug}/guide/approve?locale=en` — admin only
- `POST /api/v1/admin/destinations/{slug}/guide/request-changes?locale=en` — admin only; JSON body `{"reason":"Please verify details"}`
- `POST /api/v1/admin/destinations/{slug}/pois/{poi_slug}/submit` — editor/admin
- `POST /api/v1/admin/destinations/{slug}/pois/{poi_slug}/request-changes` — admin only; same JSON body

## Install (Windows PowerShell)

Run from the **project root**, assuming the patch is in Downloads:

```powershell
cd D:\Tourismo\Tourismo
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase2_Part3_Rich_Destinations_Review_Changes_Only.patch"
git apply --check $patch
git apply $patch
# No database volume deletion.
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
docker compose --env-file .env -f infra/compose.yaml logs --tail=60 app
```

If `git apply --check` fails, stop and inspect the conflicting files; do not force apply or overwrite local customizations.

## Smoke tests

```powershell
Invoke-RestMethod 'http://localhost:8000/api/v1/destinations/galle/photos'
Invoke-RestMethod 'http://localhost:8000/api/v1/destinations/galle/pois'
Invoke-RestMethod 'http://localhost:8000/api/v1/destinations/sigiriya/guide'
```

Open `/destinations/galle`, `/destinations/sigiriya`, and `/admin`. Existing photo records from Phase 2.2 will appear; destinations with one photo will show one large credited photo. To test multiple thumbnails, add a second **different**, licensed Commons file to one destination using `/admin`.

DBeaver checks:

```sql
SELECT version_num FROM alembic_version;
SELECT d.slug, p.slug AS attraction, p.latitude, p.longitude, p.content_status
FROM poi p JOIN destinations d ON d.id = p.destination_id
WHERE p.latitude IS NOT NULL ORDER BY d.slug;
SELECT content_status, COUNT(*) FROM destination_guides GROUP BY content_status ORDER BY content_status;
SELECT content_status, COUNT(*) FROM poi GROUP BY content_status ORDER BY content_status;
SELECT action, reason, occurred_at FROM audit_events ORDER BY occurred_at DESC LIMIT 20;
```

## Accuracy and limitations

- The four seeded coordinates are **UNESCO heritage property reference locations**, not official entrances or pedestrian directions. Sources: https://whc.unesco.org/en/list/451/ , https://whc.unesco.org/en/list/450/ , https://whc.unesco.org/en/list/200/ , and https://whc.unesco.org/en/list/202/ .
- Do not infer remaining destination coordinates or fabricate opening hours, ticket prices, booking availability or travel durations.
- Existing 18 Phase 2.2 Commons image records remain remote, subject to internet availability and Commons hosting. Verify each file's creator/license on its original page before publishing additional ones. No new external image assets are bundled here.
- A manual editorial reviewer remains responsible for checking source content and image licenses; entering an HTTPS URL alone does **not** verify accuracy.
- Phase 5 will implement interactive 2D maps and routing. Phase 2.3 provides links to externally rendered reference points, not a routing engine.
- Full production browser build and PostGIS migration require a Docker-backed test environment. Backend tests without a live Postgres instance do not prove these deployments.
