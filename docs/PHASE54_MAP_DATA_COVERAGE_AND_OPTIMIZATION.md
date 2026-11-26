# Tourismo Phase 5.4 — Map Data Coverage and Optimization

**Release scope:** Viewport-aware public map queries, capped payloads, deterministic in-browser marker grouping, and an editor-only source-quality dashboard. **No new migration** and **no invented tourist destinations, provider locations, routes, or coordinates.**

**Depends on:** Installed Phase 5.1 with location-links and Phase 5.2 + 5.3 source and migrations through `0015_location_links`. Users should confirm Phase 5.3 deployment with `scripts/verify-phase53.ps1` before installing this patch.

## Changes

1. `GET /api/v1/map/viewport` returns `{points,has_more,limit}` with optional `kind`, `south`, `west`, `north`, `east`, `limit` (20–250; default 180). Responses are capped at the **server**, not merely in React. Invalid/oversized bounds return HTTP 422. Public `GET /api/v1/map/points` is **unchanged** for Phase 5.1–5.3 callers.
2. Each category fetch is bounded to `limit + 1` and combined in round-robin order. That prevents a dense destination catalog from crowding all service or attraction markers out of a mixed result, and makes `has_more` dependable. The API never claims a total count from a truncated result.
3. `/map` refreshes only when its visible view or category changes; overlapping requests are debounced and stale requests are aborted. The map uses the same location bounds as the Sri Lankan catalog. Outside-country views provide a clear message rather than fabricated pins.
4. Screen-space clustering groups dense pins at low zoom. Clicking a cluster zooms toward its members; close zoom and the accompanying list retain individual place selection, nearby discovery, details, and Add to trip. Clusters are a frontend visualization, not new or combined database records.
5. Published-service pins continue using the existing **independent listing approval**, rejected/expired company rules, and business-verification badge calculation. Fictional demo providers, private documents, drafts and unpublished revisions are not returned.
6. `GET /api/v1/admin/geo-quality` requires an actual editor/admin account and reports **public content** with missing coordinates, missing links, locations outside a broad Sri Lanka review box, or shared coordinates. It is **read-only**: a warning is not evidence that a business is false or a location must be moved.
7. `/admin/geo-quality` renders that report and is reachable from the signed-in editor/admin account menu (desktop and mobile). Editors correct destinations/attractions through Content Studio and vendor-location changes through normal approval workflows.
8. The map fetch path avoids loading photos and listing-revision collections that are not needed by a map. No schema/index change is introduced without real PostGIS EXPLAIN measurements.

## What was deliberately *not* done

- No automated Google/OSM Places scraping, bulk invented pin seeding, or guessed geocoding. Coordinate records must be sourced, licensed/allowed for this map, and reviewed by an editor. The empty [source template](PHASE54_LOCATION_SOURCE_TEMPLATE.csv) is provided for assembling real evidence; it does not pre-populate data.
- No **100+ real verified pins** claim. Earlier Phase 5.1 automated checks confirmed **four** public mapped points at that time. The actual count after local edits must be obtained from the deployed API.
- No unmeasured GiST index migration. PostgreSQL already has spatial indexes from earlier migrations; run [SQL explain probes](../scripts/phase54-map-query-plans.sql) against your own database, record actual times and examine index/scan behavior before changing any indexes.
- No booking or route/time calculation; line segments and distances elsewhere in the app are not roads.
- No changes to Admin.tsx, ListingManagement.tsx, Clerk, PostgreSQL volumes, `.env`, Docker Compose, or existing map-link/mouse-wheel features.

## Installation (Windows PowerShell 5.1)

```powershell
cd D:\Tourismo\Tourismo
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase54_Map_Coverage_Optimization_Changes_Only.patch"
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch conflict — stop without applying.' }
git apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch failed — stop.' }
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase54.ps1
```

You should still see Alembic version `0015_location_links`.

**Rollback:** Commit your working code before applying this release if possible; `git apply -R` of the same patch reverts only this release when there are no subsequent edits. For a failed build, Docker usually keeps the last successfully deployed container running. **Never delete database volumes to roll back a frontend patch.**

## Manual acceptance checklist

- [ ] Phase 5.2 and 5.3 verifiers pass on your local installation.
- [ ] Docker Vite TypeScript compilation succeeds; `http://localhost:8000/map` renders with attribution.
- [ ] Pan and zoom: the list refreshes with only visible-area locations; rapid movements do not show stale results.
- [ ] Zoomed-out 100+ **synthetic test-only** markers group cleanly; clusters respond to clicks/taps. Real production map contains only sourced records.
- [ ] At close zoom individual markers and list actions remain usable on a laptop, phone and keyboard.
- [ ] A dense region displays the `has_more` / zoom-in instruction instead of suggesting every point was loaded.
- [ ] Change map category: only requested public kinds appear; unverified published businesses have **no** verified badge.
- [ ] `/map/points`, `/nearby`, `/plan` and `/saved` still work as before.
- [ ] Editor/admin can visit `/admin/geo-quality`; guests receive HTTP 401 from the audit API.
- [ ] Correct a destination using a genuine coordinate source; new pin appears in map viewport without changing existing source/approval policy.
- [ ] Run `scripts/phase54-map-query-plans.sql` in a **local/test PostGIS DB**, record actual timings, inspect existing indexes. Full performance SLA requires realistic data/traffic and has not been measured here.

## Verification

Unit tests cover bounds, bounded/truncated response semantics (the viewport is *capped*, not paginated), fair kind interleaving, guest permission enforcement, missing source/coordinates, suspicious locations and 120 synthetic map markers. Full backend test suite should pass with five PostgreSQL-only tests skipped in environments without a running PostGIS test DB. The frontend was syntax-parsed; npm registry access and actual Vite browser behavior must be confirmed in the deployment environment.

## Risks, limitations and future data program

- At present the map can still be sparse. Add authentic coordinates to high-priority destinations, then attractions, then real business listings. Human reviewers should confirm precise entrances when possible; **map center ≠ property pin**.
- The audit has a 5,001-record memory bound and shows at most 80 issues per response by default. It clearly labels partial scans/queues, not a full export for larger data sets.
- Shared coordinates are informational (several attractions or services can legitimately share a building), never automatic rejections.
- Nearby discovery currently still uses its separate PostGIS radius API, and saved-trip map resolution remains unchanged.
- Large public map areas can legitimately exceed the 180-point viewport limit. Users must zoom in; the map does not silently invent a total or pretend that clusters include unloaded pins.
- Public OSM tiles are for development and limited compliant use only; production requires an appropriately licensed provider, correct attribution, caching and compliance with the provider policy: https://operations.osmfoundation.org/policies/tiles/ . The existing configured tile URL determines the provider; this update does not send precise browser geolocation without permission.
