# TOURISMO — Phase 4.2: Advanced Listings (increment 1)

**Baseline:** Phase 4.1 Service Listings + the optional fictional demo-catalog source patch.
**Migration:** `0011_advanced_listings` (down-revision `0010_service_listings`)
**Delivery:** Changes-only patch; does not replace `.env`, Docker Compose, Clerk configuration, the database volume, or the Phase 4.1 demo seed.

## Capabilities

1. **Family room suitability** — accommodation room types can express optional minimum/maximum child ages and maximum total guests, in addition to adult/child capacity. The visitor can enter adults and comma-separated child ages on a listing detail page. For approved/published listings the backend evaluates room *capacity compatibility* using the saved values. This does not check inventory, availability, actual child surcharges, or prices, and does not book rooms.
2. **Map reference** — vendor may propose an optional latitude/longitude *pair* with a public HTTPS source URL and a short location note. Published pages show a link to OpenStreetMap with clearly labeled vendor-supplied, not independently verified, coordinates. The source must pass syntactic validation; admin must independently verify location accuracy before approval.
3. **Province discovery filter** — visitors can filter published service listings by province while retaining category, district, and search filters.
4. **Safe published listing revisions** — a vendor owner or manager can save a *private full replacement draft* (including text, category-specific details, coordinates, and credited photo references) while the existing approved version stays online. Submitted revisions can only be approved or returned with feedback by a separate platform administrator. Source business must remain independently approved. All decisions are audited. The listing itself stays published while a revision is submitted or returned.
5. **Photo review as part of revisions** — photographs are never edited directly on a published listing. They are proposed as sourced image references in the revision, and become live only after approval.

## Preserved business rules

- Guest discovery remains anonymous; tourist booking and payment are NOT implemented.
- Fictional development businesses remain in `draft`; the demo catalog is only accessible when explicitly enabled in development, and cannot be mistaken for real availability.
- An application signup is never automatically a platform administrator.
- Business verification and public listing publication remain separate approvals.
- Owners/managers may prepare revisions; vendor staff cannot change them.
- Admin reviewers cannot approve listings from an organization they own or belong to.
- Admin revision decisions use the existing privileged-MFA dependency.
- Existing listings, photos, user profiles, trips, licenses, and sample data are not rewritten by the migration.

## Installation — Windows PowerShell

From `D:\My Projects\Tourismo\tourismo_app`:

```powershell
cd 'D:\My Projects\Tourismo\tourismo_app'

# The baseline should be 0010_service_listings; verify current image before patch.
docker compose --env-file .env -f infra/compose.yaml exec app alembic current

$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase4_Part2_Advanced_Listings_Changes_Only.patch"
git apply --check $patch
# Only if the compatibility check passes:
git apply $patch

docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
docker compose --env-file .env -f infra/compose.yaml exec app alembic current
```

Expected Alembic version: **`0011_advanced_listings`**. Do not run `docker compose down -v`. If `git apply --check` fails, stop; your local source differs from the baseline. Don't force it or blindly overwrite the working project.

No additional `.env` variables or Docker services are required. DBeaver on `127.0.0.1:5432` and ClamAV volumes remain untouched.

## User acceptance walkthrough

### Visitor (approved listings)

- Visit `/listings`, optionally choose province/category/district.
- Open a **real published accommodation** listing (not an unverified demo).
- Enter adult count and child ages, e.g. `4, 8`.
- Check indicated single-room suitability. No booking, availability or final family price is claimed.
- If coordinates were independently reviewed and supplied by the vendor, open the map reference and source link.

### Development demo

- Visit `/demo/listings` with `APP_ENVIRONMENT=development` and `ENABLE_DEMO_CATALOG=true`.
- Open fictional accommodation listing; the family-fit form runs **local preview logic** only and is explicitly labeled fictional. It does not use the verified public API or publish the business.

### Vendor/editor

- With an **approved** business, create and submit a listing as before. Existing drafts are unaffected.
- For a real **published** listing, open `/vendor/listings`; select the service.
- Edit the proposed details and/or credited gallery and click **Save private revision**.
- Live page should still show the old approved content.
- Click **Submit saved revision for review**; the private editor locks while submitted.

### Platform admin

- Use an independent platform-admin Clerk account; navigate to `/admin/listings`.
- Review the **Published-listing revisions** queue, check every changed claim, rates, coordinates and license source, then approve or request changes with a reason.
- On approval, the replacement becomes public atomically. On changes-requested, old public data stays unchanged while the vendor can revise the proposal.

## New API contracts

| API | Access | Description |
|---|---|---|
| `GET /api/v1/listings?province=Central` | Public | Published/approved listings filtered by province |
| `GET /api/v1/listings/{slug}/family-fit?adults=2&child_ages=4&child_ages=8` | Public | Non-booking room capacity + age compatibility; approved/published accommodation only |
| `POST /api/v1/vendor/organizations/{org_id}/listings/{listing_id}/revisions` | Owner/manager | Save private full replacement proposal; optional `photos` field (omitted means keep live gallery) |
| `POST /api/v1/vendor/organizations/{org_id}/listings/{listing_id}/revisions/submit` | Owner/manager | Send saved proposal to independent review |
| `GET /api/v1/admin/listings/revisions` | Platform admin | Submitted private revisions |
| `POST /api/v1/admin/listings/revisions/{revision_id}/decision` | Platform admin + privileged MFA when enforced | Decision `{ "decision": "approved" | "changes_requested", "reason": "..." }` |

The public listing response adds optional `latitude`, `longitude`, `location_source_url`, and `location_note` but **never includes private revision snapshots**. The vendor-only listing response includes `revision` when one is currently open.

## Database changes

- Add four nullable fields to `service_listings`: `latitude`, `longitude`, `location_source_url`, `location_note`. A database CHECK requires either no point or both valid coordinates plus source URL.
- New `service_listing_revisions`: proposed snapshot JSONB, author, independent reviewer, review status, feedback, timestamps. Partial unique index prevents more than one open draft/submitted/changes-requested revision per listing.
- New room age fields are stored in the existing `details` JSONB after validation. Existing JSONB data remains valid and is not backfilled with assumed age policies.

### Read-only DBeaver checks

```sql
SELECT version_num FROM public.alembic_version;
SELECT COUNT(*) AS listing_count FROM public.service_listings;
SELECT status, COUNT(*) FROM public.service_listing_revisions GROUP BY status ORDER BY status;
SELECT slug, status, latitude, longitude, location_source_url
FROM public.service_listings ORDER BY created_at DESC LIMIT 20;
-- Demo listings remain drafts:
SELECT COUNT(*) AS published_demo FROM public.service_listings
WHERE slug LIKE 'tourismo-demo-%' AND status = 'published';
```

## Testing and limitations

- Backend regression suite: **79 passed, 5 skipped** using `PYTHONPATH=apps/api python -m pytest -q apps/api/tests`. Skipped tests require a disposable PostgreSQL test database.
- Changed TSX/TS files: TypeScript parser syntax validation passed. **Full Vite build, typecheck, actual PostGIS migration and authenticated browser workflow are not verified in the build environment**, so validate them through Docker on Windows.
- No image uploads, real-time rates, bookings, payment processing, live route navigation, geocoding, or live inventory in this phase.
- A room's ability to fit one family is only an informational *single-room* check: it does not optimize multi-room allocation.
- A source URL or manual admin check does not prove exact entrance location. Providers and admins must verify submitted coordinates and licensing externally.
- Production requires an independent security, role/MFA, PostGIS, backups, monitoring and browser/accessibility acceptance test before public deployment.
