# Tourismo — Phase 6: Saved Trip Editing & Detailed Budget Management

**Release type:** changes-only upgrade on top of Phase 5.4.  **Database migration:** none (existing `0015_location_links`).

## Purpose

Tourismo already supports guest itinerary planning, public-place references, saved trip snapshots and a simple one-amount-per-category estimate. Phase 6 extends that workflow with detailed daily expenses, safe editing of saved cloud trips, duplication and explicit deletion. It remains a **travel-planning and discovery application**, not a booking or payment platform.

## Scope delivered

| Area | Implementation |
|---|---|
| Expense lines | Multiple expenses in the same category; description, day or whole-trip assignment, minimum/expected/maximum amount, user-provided source label and optional personal confirmation indicator |
| Group costs | Integer LKR minor-unit arithmetic, expected spend per traveler, combined group costs, daily totals, category totals, unassigned totals, budget-limit remaining amount and maximum-over-limit warning |
| Compatibility | Legacy expenses without a `day` load as trip-wide/unassigned; old manual itinerary stops and stable public-place references remain valid |
| Cloud editing | An authenticated owner can open an existing trip from `/saved` with `edit_trip=<id>`, modify it in `/plan`, and explicitly save changes |
| Conflict protection | Every PATCH carries `expected_version`; PostgreSQL UPDATE conditions on trip ID, owner ID and version in one atomic statement; stale saves receive HTTP 409 and preserve the user's draft |
| Copy | An editor can keep the current draft as a new independent saved trip with a fresh client draft ID |
| Delete | Explicit confirmed deletion of one owner-scoped saved trip; no bulk deletion or third-party access |
| Map integration | Map / nearby result links carry the saved trip ID through `edit_trip` when navigated from a saved-trip editor. The planner reloads that owner-scoped trip before appending the selected public place |
| Privacy | Private trip data requires real Clerk authentication; the guest session draft is not overwritten with loaded cloud trip data |

## API changes

| HTTP | Endpoint | Authentication | Behavior |
|---|---|---|---|
| `POST` | `/api/v1/trips/preview` | Guest | Stateless preview with `by_category`, `by_day`, `unassigned`, `per_traveler_expected_minor` (plus original keys) |
| `POST` | `/api/v1/trips` | Signed in | Existing idempotent save; response also includes `version` |
| `GET` | `/api/v1/trips` | Owner | List saved trips, including `version` and new preview totals |
| `GET` | `/api/v1/trips/{id}` | Owner | Load a private saved trip for editing |
| `PATCH` | `/api/v1/trips/{id}` | Owner | Body `{"expected_version": 1, "draft": {...}}`; atomically updates when version matches, increments version; 409 on conflict, 404 if not owner / missing |
| `DELETE` | `/api/v1/trips/{id}` | Owner | Permanently delete own trip, HTTP 204; 404 for missing / not owner |

The `client_draft_id` stays immutable on PATCH, preserving the existing unique `(owner_id, client_draft_id)` constraint and POST idempotency semantics. On a fresh copy, the browser creates a different UUID and performs a new POST.

### Example budget item

```json
{
  "category": "accommodation",
  "description": "Two nights in Kandy",
  "day": 2,
  "minimum_minor": 1200000,
  "expected_minor": 1500000,
  "maximum_minor": 1800000,
  "is_confirmed": false,
  "source_label": "My personal estimate"
}
```

**Units:** amounts are in cents of LKR (`1500000` = LKR 15,000.00). The app does not fetch provider prices. `day` can be `null` / omitted for a whole-trip expense. Max 80 budget entries; cost ranges require minimum ≤ expected ≤ maximum. The user interface offers 31 day choices, matching the current trip-day upper bound. It does not automatically book nights, allocate costs across different days, or verify a source label.

### Concurrent-write example

1. Sign into Tourismo with the same account on two browser tabs.
2. In both tabs open the same saved trip while it is version 3.
3. Tab A updates it, sending `expected_version=3`. Database transitions version 3 → 4.
4. Tab B sends `expected_version=3`; `PATCH` returns **409**, and Tab B's draft remains visible. It is **not overwritten**.
5. Tab B may open the saved version separately and reconcile changes manually, or choose **Keep my changes as a separate trip**.

The server uses a compare-and-swap SQL statement and refreshes the updated record before returning a response; this is essential because the project uses `Session(expire_on_commit=False)`.

## User operating workflows

### A. New guest trip budget

1. Open `http://localhost:8000/plan`.
2. Select a destination, group size and optional dates. Add itinerary stops or select attractions from `/map` or `/nearby`.
3. In **Your budget breakdown**, add as many budget lines as needed (up to 80). Select category, description, trip day, and three amounts (minimum/expected/maximum). Use **Whole trip** for costs not tied to one day.
4. Review the daily/category totals, expected total, maximum and per-traveler estimate.
5. Click **Validate my budget with API**. The API does not record the preview.
6. To save across devices, sign in and explicitly confirm the cloud save.

### B. Edit an existing private trip

1. Sign in and open `/saved`.
2. Select **Edit this trip**. This explicitly opens `/plan?edit_trip=<saved-trip-id>` and loads the owner-scoped draft.
3. Edit travel days, stops, notes, group sizes and budget lines. Edits are **not** auto-saved.
4. Choose **Save changes to trip**, confirm, and check that the version increases.
5. If a conflict appears, do not refresh or close the tab before copying/reconciling your changes; use **Keep my changes as a separate trip** if needed.
6. **Save as a new trip** creates a fresh guest draft ID. Saving it creates another private trip, leaving the original unchanged.

Map / nearby links launched from the cloud editor carry the saved-trip ID and return to the appropriate saved trip. Save unsaved changes **before** leaving for the map: the private cloud editor is intentionally not written to guest browser storage.

### C. Delete one saved trip

1. In `/saved`, click **Delete** on the correct trip.
2. Confirm the browser's explicit permanent-deletion prompt.
3. Tourismo deletes that owner's record; no payment, itinerary from another account or vendor profile is changed.

## Security and compatibility

- All new private routes use the same verified-user dependency as existing saved trips; every UPDATE and DELETE is scoped by `owner_id`.
- Invalid expected versions receive HTTP 422. Stale versions receive 409; no forced overwrite or last-write-wins.
- Guest previews are stateless. Guest GET/PATCH/DELETE of private trips return 401.
- Stored linked public place IDs remain references; map visualization continues rechecking publication state.
- No new tables or migrations, no `.env`, Docker Compose, Clerk, ClamAV, vendor-listing, business-verification or PostGIS changes.
- No automatic provider quotes, payments, currency exchange, group settlements, or routing durations. These require separate future design and acceptance.

## Install (Windows PowerShell 5.1)

```powershell
cd D:\Tourismo\Tourismo
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase54.ps1
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase6_Trip_Budget_Changes_Only.patch"
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Stop: patch conflict; do not apply.' }
git apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Stop: patch apply failed.' }
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase6.ps1
```

Expected Alembic revision: `0015_location_links`. Do not remove Postgres volumes or overwrite your customized Compose. Make a DB backup before applying a release when using real trip data, even if this release has no migration.

## Local acceptance tests (mandatory)

- [ ] Phase 5.4 verifier passes before installing Phase 6.
- [ ] Full `npm run build` / Docker build passes, including UTF-8 guard, strict TypeScript and Vite production build.
- [ ] Guest planner shows budget line editor with ranges, category and day subtotals.
- [ ] Existing saved trip's legacy budget without `day` appears under whole-trip expenses.
- [ ] API preview reports correct LKR amounts in **minor units**, and guest cannot access saved trip APIs.
- [ ] Signed-in user can create, edit, save and re-open the same saved trip; version increments and new data is present.
- [ ] Two-tab stale save returns HTTP 409 and preserves unsaved draft.
- [ ] Different user cannot read, update or delete the saved trip.
- [ ] Save as a new trip leaves the original unchanged; delete uses explicit confirmation.
- [ ] Editing a saved trip, navigating to `/map` after saving, and adding a public place returns to the same private trip.
- [ ] Previously working map, nearby, geo-quality report, source links and vendor listing approvals still work.
- [ ] Test with mobile widths and longer text descriptions; invalid range warning should be accessible and readable.

## Automated checks and limits

Backend regression suite: `cd apps/api; python -m pytest -q` (pytest dependency must be installed in the **test environment**, not the production image). Frontend Vitest file: `apps/web/src/lib/budget.test.ts`, run `npm test` when dependencies are available. Read-only deployed verifier: `scripts/verify-phase6.ps1`.

This development environment does not have npm registry access or a live production-like PostGIS test DB. Passing syntax parsing and Python unit tests **does not** establish that the local Docker build or two-tab browser workflow passed. Run the acceptance checklist after installation.
