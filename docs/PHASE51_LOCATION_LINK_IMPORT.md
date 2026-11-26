# Tourismo — Shared map links, exact pins, and destination locations

## Why this change is needed

Tourismo Phase 5.1 used map clicking or manually typed coordinates. That is slow and inaccurate when a business or place already has a shared map pin. More importantly, the destination admin form couldn't write the `destinations.location` PostGIS field at all, and previously published destinations couldn't be given map coordinates through the Content Studio. Attraction coordinates shared a content citation, so a link to a map could accidentally be confused with an editorial source.

## The new user experience

1. In **Content Studio → New destination**, **Destination map location**, or **Add attraction**, find **Pinpoint this location**. In **For businesses → Manage listings → Location**, the same widget is available for new listings and proposed revisions.
2. In Google Maps, share a **pinned location** (not just a search phrase) and paste its HTTPS URL. OSM marker links, Apple Maps and Bing Maps links with coordinates are also supported. Short `maps.app.goo.gl` and legacy `goo.gl/maps/` links are resolved through allowlisted HTTPS redirects.
3. Click **Find location from link**. The backend returns coordinates only if present in the shared URL. It doesn't scrape third-party place details or call Google Places/Geocoding APIs.
4. Tourismo opens the map and shows an **orange suggested marker**. Google Maps viewport `@lat,long` / OSM `#map=` and other camera centers are identified as **approximate map centres**, not exact venue pins. A check box requires manual confirmation for these.
5. Compare the point against the correct entrance, business location or attraction access point, optionally click the map to adjust, then choose **Use this location**. The original HTTPS link is attached to the form as provenance. Finally save the destination/POI/listing; resolving the link alone never persists or publishes it.
6. The public `/map` continues to include only approved/public destination/POI records and independently published, eligible service listings. Fictional demo providers remain excluded. A vendor's update to a published listing still follows the **revision review** workflow. Business verification remains separate from listing content review.

**Limitations:** A link containing only a place name, a Google Place ID, or a dynamic map page without coordinates cannot be reliably resolved offline. The UI explains this and offers the manual picker. Automatic place-name geocoding would require a separately licensed provider and changes to consent/billing/attribution rules. No provider API key is necessary for parsing shared coordinates. This does not imply endorsement or location verification by Google, Apple or OpenStreetMap.

## Security and integrity safeguards

- Authentication required (`POST /api/v1/map/resolve-location`). No business verification requirement for vendor drafts; platform-editor status controls destination writes. Admin-only update for **published** or **sample** destination/attraction coordinates; draft content editors may save drafts.
- A strict HTTPS **domain allowlist** permits only designated map-provider hosts. Short link redirects are validated **at every hop**, with no arbitrary URL fetching, local IPs, custom ports, proxy environment or HTML scraping. Requests use explicit timeouts, 4 redirects maximum, and a per-IP rate guard. Production needs an edge/Redis shared rate limiter if scaling across replicas.
- Coordinates must be finite, valid, paired with a source URL, and fall inside Sri Lanka for resolved map links. Destination/attraction coordinate sources are kept **separate** from editorial guide and POI citations.
- Pasting a link returns a *proposal*, not an auto-published coordinate. A map view centre requires explicit acknowledgement. Location additions/edits remain audited in the admin system.
- No scraping of Google Maps place descriptions, images, reviews or other Maps Platform data. Google Geocoding and Places APIs are not used: their terms may prohibit displaying their content on a non-Google map.

## Changed files and migration

- Backend: `maps/location_links.py` (parser and safe redirect resolution), `maps/routes.py` (authenticated endpoint), `admin/routes.py` (destination create/update and attraction create/update), `core/models.py`, `geography/routes.py`, `main.py` (small per-IP limiter).
- Frontend: `features/Map.tsx` (shared widget), `features/Admin.tsx` (new/existing place and attraction locations), `features/ListingManagement.tsx` (vendor listings and revisions), `lib/api.ts` (types, endpoints).
- Alembic: `0015_location_links.py` adds **nullable** `location_source_url` to `destinations` and `poi`. Existing geometry, listings, documents and user data remain unchanged. `service_listings` already has a `location_source_url` field. No backfill/fake coordinates.
- Verification: updated `scripts/verify-phase51.ps1` for Windows PowerShell 5.1 and migration 0015; `scripts/verify-location-links.ps1` wrapper; tests in `test_phase52_location_links.py`.

## Install safely (PowerShell from project root)

First back up PostgreSQL data if you're retaining real editor/vendor content:

```powershell
cd D:\Tourismo\Tourismo
$backup = "tourismo-before-location-links-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
$dbContainer = docker compose --env-file .env -f infra/compose.yaml ps -q db
docker compose --env-file .env -f infra/compose.yaml exec -T db pg_dump -U tourismo -d tourismo -Fc -f /tmp/tourismo-before-location-links.dump
docker cp "${dbContainer}:/tmp/tourismo-before-location-links.dump" ".\$backup"
```

Apply **only this changes-only patch**, not any previous Phase 5.1 patch again:

```powershell
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase51_Location_Links_Changes_Only.patch"
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch did not match; stop without modifying files.' }
git apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-location-links.ps1
```

Expected migration: `0015_location_links`. You should continue to see the existing four published map points until you add more sourced locations. No volumes must be deleted; no Docker Compose or `.env` replacement.

## Acceptance scenarios

- **Admin/editor:** create a destination with no coordinates; it remains a draft. Later open **Destination map location**, import a pinned Sri Lanka location, verify on preview, save, publish normally. If already published, an administrator can update its position and the next public `/map` refresh shows the change.
- **Attraction:** create a draft POI using a separate editorial source *and* an optional shared map link. Published POI location changes are admin-only.
- **Vendor:** unverified business can add a link to a new listing; content requires independent approval. A published listing's location change goes through the existing listing revision approval; no silent public change.
- **Safety:** reject an unknown or internal HTTPS URL, redirects to arbitrary hosts, `http://`, links without coordinates, and points outside Sri Lanka. Do not infer that viewport centres are exact pins.
- **Regression:** guest discovery, public map, listing verification badge, existing data and UTF-8 guard must still work.

The script checks database migration, API readiness, public markers, and resolver authentication. **A real maps.app.goo.gl redirect and browser workflow require live testing on your machine.** The local unit tests mock redirects without connecting to Google.
