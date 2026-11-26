# Tourismo — Phase 5.1: Interactive Sri Lanka map

**Status:** Implemented in source; verify the local Docker build and database queries before accepting this phase.
**Prerequisite:** The pre-Phase-5 vendor badge/destination UX updates, corrected `Admin.tsx`, and migration `0014_vendor_experience` are installed.

## What is available

- `/map` — responsive, interactive map and synchronized results list, no account required.
- `/api/v1/map/points` — anonymous read-only records from existing PostGIS/POI/listing data.
- `/api/v1/map/config` — public map tile configuration; production tiles are disabled until a provider is configured.
- Destination, attraction, and service markers with distinct colors, category filter, place-name/district search, and links to existing detail pages.
- Verified business indicator displayed **only** for independently verified businesses. Unverified businesses have no verified badge; eligible published listings are still shown.
- Optional user-triggered browser geolocation. No automatic location permission request or storage.
- Map-click coordinate picker in the editor's **Add attraction** flow and the vendor's **Listing location** step. Choosing a point fills two fields; an identifiable HTTPS location source is still required by the existing backend.
- Links to `/map` in main navigation, Discover, destination pages, and the real Services directory.

## What appears as a marker

**Destinations:** `destinations.location` must contain a stored PostGIS point and `content_status` must be `published` or `sample`.

**Attractions:** `poi.latitude` and `poi.longitude` must both exist; POI and destination must both have a public/sample status. A map marker is an approximate reference and not a confirmed entrance or route.

**Services:** listing must be published, the business must not be rejected/expired, no expired business evidence is permitted, and the listing must have coordinates. This reuses `_public_query()` from the Phase 4 listings API and intentionally allows eligible **unverified** businesses without a badge. No private business applications, credentials or documents are returned.

**Demo listings:** not shown. They remain fictional, draft records in the separate `/demo/listings` experience.

The existing 117-destination starter catalog mostly consists of directory records, not geocoded site records. Those entries remain searchable in `/discover` but are **not placed at invented coordinates**. To increase map coverage, editors should add source-checked coordinates to attractions and vendors should add their actual service coordinates. Phase 5.2 will add stronger source governance and viewport/radius-driven discovery.

## Tile provider configuration

For **local development**, the API uses OpenStreetMap raster tiles, with visible attribution. You must respect the [OSMF tile usage policy](https://operations.osmfoundation.org/policies/tiles/). The map browser downloads tiles directly from the tile server; map usage may therefore be visible to the tile provider.

For **production**, the API returns `tile_url: null` unless you explicitly configure a licensed raster tile provider with a browser-accessible HTTPS template. Add to the root `.env`:

```env
MAP_TILE_URL=https://YOUR-LICENSED-TILE-PROVIDER/{z}/{x}/{y}.png
MAP_TILE_ATTRIBUTION=© OpenStreetMap contributors | Your map provider attribution
```

A server-side **secret** must not be used in `MAP_TILE_URL`, because this URL is sent to browsers. If the provider requires a token, use a domain-restricted public browser key, or an approved server-side proxy with separate security controls. The template must include `{z}`, `{x}` and `{y}`. Confirm provider attribution and permitted usage for your deployment.

Recreate the application container after editing `.env`:

```powershell
docker compose --env-file .env -f infra/compose.yaml up -d --force-recreate app
```

No modification to `infra/compose.yaml` is required for this phase.

## Installation: changes-only patch

From `D:\Tourismo\Tourismo` in PowerShell:

```powershell
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase5_Part1_Interactive_Map_Changes_Only.patch"
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch did not match local files. Do not force-apply.' }
git apply $patch
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
```

For the first map build, Docker will download Leaflet 1.9 and React Leaflet 5 as npm dependencies. Internet access to the npm registry is required once. React 19 is already used in Tourismo.

**No new Alembic revision** is introduced. The database should remain at `0014_vendor_experience`; never run `docker compose down -v` for this update.

## Practical test script — all roles

### Guest / tourist
1. Open `http://localhost:8000/map` without signing in.
2. See mapped attractions with real stored coordinates (including the initial UNESCO reference sites, if migration 0005 seeded them), or an informative empty list when none are geocoded.
3. Filter `Attractions`, then search by `Kandy` or `heritage`. Select a result: map should center on it. Select a pin: its popup should open.
4. Open its Details link: return to the corresponding approved/sample destination page.
5. Switch to `Tourism services`. Only currently published, eligible, geocoded businesses appear; no draft or fictional demo businesses appear.
6. For a service from an approved business, see **Verified business**. For an otherwise eligible unverified business, no badge appears.
7. Click **Use my location**: browser permission should be requested *only now*. Decline permission; map remains usable.
8. On a phone-width browser, the map/list should stack vertically. Check keyboard filters, popup links and navigation.

### Content editor
1. Sign in with an authorized editor account, open `/admin` and the **Add attraction** area.
2. Click **Choose approximate point on map**, click a site, and verify latitude/longitude fields fill in.
3. Supply an authoritative HTTPS source URL and source name, then save the unpublished POI draft.
4. Submit it through the existing review flow; an independent administrator must approve it before the public map can show it. Draft locations never appear on the map.

### Vendor owner / manager
1. Sign in, visit `/vendor/listings`, and open the listing wizard's location section.
2. Click the map picker, select the real property/service point, and confirm numeric coordinates are filled.
3. Supply a genuine location source HTTPS URL. A random click is **not** proof of geographic accuracy.
4. Submit the complete listing; independently reviewed published listings become eligible for map display.
5. Confirm the optional verified badge is calculated from the *business verification state*, not from listing approval.

### Administrator
1. Approve/reject listing and POI submissions using existing admin tools.
2. Ensure rejected/expired business listings, draft POIs and unpublished listing revisions never leak onto `/map`.
3. Confirm demo listings remain isolated and labeled within `/demo/listings`.

### API and DBeaver checks

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
Invoke-RestMethod http://localhost:8000/api/v1/map/config
Invoke-RestMethod http://localhost:8000/api/v1/map/points
Invoke-RestMethod 'http://localhost:8000/api/v1/map/points?kind=attraction'
powershell -ExecutionPolicy Bypass -File .\scripts\verify-phase51.ps1
```

```sql
SELECT version_num FROM public.alembic_version;
SELECT COUNT(*) FROM public.poi WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
SELECT COUNT(*) FROM public.service_listings
  WHERE status = 'published' AND latitude IS NOT NULL AND longitude IS NOT NULL;
SELECT COUNT(*) FROM public.destinations WHERE location IS NOT NULL;
```

## Security and acceptance

- Backend has automated tests for geographic input validation, public status restrictions, original publication guard, verified/unverified badge calculation and absence of private fields.
- Public map endpoint rate-limited by the same simple local-process guard as existing public searches. This is **not** a substitute for distributed production rate limiting.
- Query returns at most 150 destination, 200 attraction and 200 service markers per call (first map slice). These are bounded for pilot usage; viewport-driven pagination and marker clustering belong to Phase 5.2/5.4.
- No booking, inventory, provider pricing confirmation, driving distance or route duration is claimed.
- Full React/Vite/Docker and live PostgreSQL/PostGIS behavior must be verified locally before accepting Phase 5.1. Offline test environments cannot download the new npm dependencies.
