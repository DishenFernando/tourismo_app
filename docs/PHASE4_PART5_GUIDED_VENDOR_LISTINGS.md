# TOURISMO — Phase 4.5, Part 1: Guided Listing Creation & Private Quick-Start

**Base:** Phase 4.4 (`0013_onboarding_media_ux`) with the existing demo catalog.
**Database schema:** unchanged. **No new Alembic revision.**
**Release type:** source-only, changes-only patch; no `.env` or Compose modifications.

## Purpose

The old listing form displayed all the fields for a business type in a single screen. A vendor could not store a listing until it met the complete `ListingWrite` schema. Phase 4.5 Part 1 improves this in two complementary ways:

1. **Title-only private starter:** a signed-in organization owner or manager can store a draft using just a service name. All other fields stay genuinely blank, never invented placeholders.
2. **Four-step editor:** Introduction → Category-specific details → Contact/location → Preview/save. Changes to an already published listing still use the private revision process.

## Walkthrough

1. Go to `/vendors`, select a business or create a private business application (Phase 4.4).
2. Go to `/vendor/listings`, select the organization, and click **New**.
3. Enter the service name. Click **Save title-only starter** to persist it privately before doing the detailed work. Otherwise fill out the short introduction and continue through the wizard.
4. The second step adapts to the organization's category (rooms/occupancy, cuisines/menu, languages/areas, vehicles/capacity, or experiences).
5. Enter a detailed description and optionally public contact data and sourced location coordinates. A public contact method is **required for publication**, not for an early draft.
6. Inspect the preview. Choose **Create private draft** / **Save draft changes** / **Save private revision**, as appropriate.
7. Only after saving a complete draft, optionally attach properly credited service photographs and submit for independent admin review. The organization must be approved to submit.

### Important security boundaries

- Quick-start requires **real Clerk authentication** and owner/manager role for the exact organization.
- `POST /api/v1/vendor/organizations/{org_id}/listings/quick-start` accepts **only `title`**. It rejects a supplied status or other unrecognized attributes. The stored status is always `draft`.
- Server enforces the existing 25-active-listings-per-organization limit on both ordinary and quick-start creation.
- An unverified business may prepare a draft but cannot submit it for publication.
- `submit` now explicitly re-checks the **complete** `ListingWrite` schema before checking category-specific data. An incomplete starter can never bypass the normal publishing rules.
- `published` listings stay unchanged while a private revision is prepared and independently reviewed.
- Content is never live from the preview or the title-only starter; the normal public directory still requires both verified organization and published listing.
- Location coordinates continue to require an HTTPS source and remain provider-supplied, not verified entrance points.
- No booking/payment, real-time availability, subscription activation or identity/role changes are introduced.

## Changed files

- `apps/api/tourismo/listings/routes.py` — private quick-start, shared quota, final validation at submission.
- `apps/api/tests/test_phase45_quick_listing.py` — identity, data limits, draft privacy and submission checks.
- `apps/web/src/lib/api.ts` — typed quick-start client.
- `apps/web/src/lib/listingWizard.ts` — step-level UI validation and readiness guidance.
- `apps/web/src/lib/listingWizard.test.ts` — UI validation unit tests (run with Vitest in the local frontend).
- `apps/web/src/features/ListingManagement.tsx` — guided wizard, preview, title-only starter, previous published-revision behavior retained.
- `scripts/verify-phase45.ps1` — read-only local smoke tests.

## Install (Windows PowerShell)

```powershell
cd D:\Tourismo\Tourismo
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase4_Part5_Guided_Listings_Changes_Only.patch"
git apply --check $patch
# Only if check passes:
git apply $patch
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
# Still on 0013 — no new migration:
docker compose --env-file .env -f infra/compose.yaml exec app alembic current
powershell -ExecutionPolicy Bypass -File .\scripts\verify-phase45.ps1
```

Do not run `git apply` twice or `docker compose down -v`. If the patch was applied and the subsequent check fails, try `git apply --reverse --check $patch` to verify that the patch is already present; do **not** run `git apply --reverse` unless intentionally uninstalling it.

## Acceptance tests

- A tourist or anonymous visitor cannot create a vendor draft.
- An owner/manager can create a title-only draft in an organization they can edit; a staff user cannot.
- Draft remains private from `/api/v1/listings` and cannot be submitted until full details/contact and organization verification are satisfied.
- Reopen an incomplete draft and complete the wizard for each of the six supported categories.
- Published listing editing still creates a private revision. The public listing is not changed until independent approval.
- Confirm that demo businesses and draft demo listings remain private.
- Verify the frontend production build locally (`docker compose ... up --build -d`), because npm dependencies were not available for a complete Vite build in the build environment.

## Deferred UX improvements

- Secure email-token invitations for organization staff (not raw UUIDs).
- Simplified vendor photo upload with an encrypted, private production media store and rights management.
- A guided license reference + document upload sequence and clearer verification progress indicators.
- Saving partially completed service-category data server-side at each step (currently the *title-only* starter is saved and the fully completed listing can be saved at the end).
- Real browser/device and PostgreSQL end-to-end acceptance tests.

These are not represented as shipped features in this increment.
