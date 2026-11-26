# Tourismo — Phase 5.2: Smart Nearby Discovery

## Purpose and boundaries

Visitors can find **publicly mapped** destinations, editorial attractions and independently published tourism services within a fixed radius of a **known map point**, selected destination or a browser-permitted temporary location. The results and the map remain synchronized. This is geographic discovery only: no booking, payment, invented travel time, or unverified entrance claim.

## Entry points

- `/nearby`: main nearby discovery view, available without login.
- `/map`: **Explore nearby places** action, plus **Nearby** for each map result.
- `/destinations/{slug}`: **Explore nearby** button.
- `/nearby?destination=kandy`: tries to use the public, mapped destination coordinates; if the destination has no pin, the UI asks the tourist to choose a mapped reference point instead.
- `/nearby?point=attraction:<uuid>` or `/nearby?point=service:<uuid>`: uses a point already present in the public map list.

Users can filter by **5, 10, 25, 50 or 100 km**, marker kind, service/attraction category and keyword. **Find nearby** submits the selected filters. Clicking a result focuses the map marker. A small circle marks the selected radius. Only the current list is displayed in the map.

## API contract

`GET /api/v1/map/nearby`

Query:

- Either `destination=<public-slug>` **or** both `near_lat` and `near_lon`.
- `radius_km` positive, <=100; defaults to 25.
- `kind`: `all`, `destination`, `attraction`, or `service`.
- Optional `category`, `q` (max 80 chars), `limit` (1–60; default 60).
- 422 for missing, contradictory or invalid coordinates/radius; 404 for non-public destination; 422 for public but unmapped destination.

Response:

```json
{
  "center": {"title":"Selected map location","latitude":7.291,"longitude":80.634,"kind":"selected_location","destination_slug":null},
  "radius_km":25,
  "points":[],
  "has_more":false,
  "distance_note":"Distances are straight-line estimates, not routes or travel times."
}
```

Each result uses the existing `MapPoint` shape plus `distance_km`. Empty arrays are valid and are never filled with dummy coordinates. The result set is capped at 60 and sorted closest first; `has_more` signals when the cap was reached and at least one more qualifying result was found.

## Publication, trust, and privacy

- Destinations and attractions must be marked `sample` or `published`; sample points remain clearly labeled.
- Service listings use `_public_query()`, the same independent moderation and rejected/expired evidence gate as `/listings` and `/map/points`.
- `business_verified` is server-derived from the business verification state; unverified but independently published services show no verified badge.
- Fictional demo providers never enter this API.
- Browser location permission is requested only after a direct **Use my location** click. The request uses temporary coordinates and does not create a user profile record.
- No private vendor documents, unpublished draft listing revisions or contact details are returned by this API.
- Distances are **PostGIS geography meters** (`ST_DWithin`, `ST_Distance`) for a straight-line distance, not actual roads.
- Existing Phase 5.1 shared-map-link validation and manual position editing are unchanged.

## Data coverage and limitations

The app previously had only four public mapped places at the last verified checkpoint. Thus a correct nearby query may return few or no results. Editorial users must continue collecting authentic, sourced coordinates using the existing Content Studio before proximity discovery can be effective nationwide. There is no arbitrary address/place-name geocoding or third-party search introduced in this phase.

The UI fetches a bounded public map list for its center dropdown; the later Phase 5.4 performance work should add paginated mapped-center search if inventory grows beyond this catalog limit. On a very large data set, spatial indexes on the geographic representation of service/attraction coordinates should be considered; measure query performance before adding indexes. The current Phase 5.2 change does not add database migrations or tables.

## Installation — changes-only

Download `Tourismo_Phase52_Smart_Nearby_Discovery_Changes_Only.patch` to Downloads.

```powershell
cd D:\Tourismo\Tourismo
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase52_Smart_Nearby_Discovery_Changes_Only.patch"
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch check failed. Stop without applying.' }
git apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch apply failed. Stop.' }
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase52.ps1
```

If patch check fails (especially `Map.tsx`), **do not force or reapply old patches**. Preserve your local edits and compare the affected file; we can make a targeted compatibility fix. No Compose or PostgreSQL volume changes are required. Existing migration remains `0015_location_links`.

## Manual acceptance checklist

1. Open `/nearby` as a guest. Choose a mapped place and search within 25 km. Check list, pin positions, radius overlay and sorting by straight-line distance.
2. Change radius (5→50 km) and category. Click **Find nearby** and confirm that the results change without showing service drafts.
3. Choose **Explore nearby** from a destination detail page. If the destination has no coordinates, verify the no-location notice and mapped-center fallback.
4. From `/map`, choose an attraction or a published service and follow **Nearby**; verify it uses that selected public point as the center.
5. Verify published service listings of unverified businesses have **no** verification badge; independently approved and verified business listings do.
6. Verify the guest location button requests browser permission only when clicked, and declining permission still leaves the map-search workflow operational.
7. Verify marker/list selection and wheel-zoom work on mouse and touchpad, including narrow/mobile screens.
8. Run `scripts/verify-phase52.ps1` in Windows PowerShell 5.1 and check the application logs for errors.

## Regression tests

Run local backend tests using the repository's Python environment:

```sh
cd apps/api
PYTHONPATH=. pytest -q
```

The new `tests/test_phase52_nearby.py` verifies validation, the public endpoint, PostGIS distance queries, search predicates, badge derivation and privacy. Complete TypeScript/Vite build and live PostGIS integration must be run against the user's Docker stack.
