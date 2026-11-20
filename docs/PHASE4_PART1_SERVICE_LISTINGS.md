# TOURISMO — Phase 4.1 | Public Tourism Service Listings

**Date:** 20 November 2026

**Baseline:** Phase 3.2, migration `0009_vendor_documents`

**New migration:** `0010_service_listings`
**Nature:** Additive; no Phase 0–3.2 data is deleted or replaced.

## What visitors can do now

The new **Services** tab (`/listings`) is anonymous and lists *only* explicitly published offers belonging to businesses currently approved for verification, with no expired evidence references. Visitors can filter by type, district and keywords, view category-specific details and credited images, and contact the provider via an explicitly public email or telephone number. All listed pricing is **indicative**. It is not an availability feed, booking confirmation or contract quote. When there are no approved listings the empty state says so; no fictional providers are seeded.

Supported listing types and structured data:

| Type | Fields added in 4.1 |
|---|---|
| Accommodation | Room-type entries, adult/child capacity, room counts, indicative nightly prices, amenities and house rules |
| Restaurant | Cuisines, dietary options, menu highlights, indicative item prices and opening notes |
| Guide | Languages, service areas, qualification notes and indicative daily rate |
| Transport | Vehicle types, passenger seats, luggage bags, service areas, indicative day rates |
| Tour operator / activity | Experience types, service areas, duration, age minimum and indicative per-person price |

**Pending Phase 4.2+:** Child-age ranges and combined multi-room family allocation rules, per-season/package rates and disclosure, cancellation terms, structured opening schedules, true media uploads and rights checks, source-verified geo pins, listing revisions without unpublishing, availability integrations, inquiries in Tourismo, searching by amenities and actual offers. Subscription and booking/payments remain separate later phases.

## What businesses can do

1. Sign in with verified Google/email and register a vendor organization in `/vendors`.
2. Obtain separate platform-admin approval for the *organization* following Phase 3 verification.
3. Open `/vendor/listings` from the account menu or vendor dashboard. Even unapproved organizations can prepare private listing drafts.
4. Create a listing (category inherited server-side from the organization; cannot be changed by browser payload), manage structured subtype data and explicitly public contacts, and add up to 10 credited HTTPS image references.
5. Submit after business verification is approved and license evidence is current. A public contact email or phone is required. Drafts cannot be discovered publicly.
6. An independent admin reviews the submitted content from `/admin/listings`, requests corrections or approves for publication. The admin must not own or belong to that vendor organization. Decisions are audited. Production sensitive approval uses the existing Clerk MFA gate.
7. Vendors can archive any listing to remove it from public discovery. Published listings cannot be silently rewritten; new revision workflow will be added in Phase 4.2.

`service_listings` stores listing identity/status, location label, user-authored copy, category-specific JSONB and explicitly public contact channels. `service_listing_photos` stores attribution details and external HTTPS URLs only; images aren't downloaded or stored on the API. `service_listing_reviews` records the admin reviewer, action, reason and time. Audit events are written in the existing `audit_events` table.

### Security boundaries

- No public route returns vendor registration numbers, private email/phone/address, verification documents, owner IDs, internal feedback, or administrator review records.
- Public reads require **both** `service_listings.status = published` and `vendor_organizations.verification_state = approved`, and filter out organizations with expired evidence. This protects users even before the Phase 3 maintenance job marks expired organizations.
- Organization membership is checked with active `owner` / `manager` / `staff` roles. Staff can read private listings but not edit/submit. Members of a different organization receive 404 for another organization's listing.
- A real platform-admin role is required for moderation. Reviewers who own/belong to the business cannot approve that business. The existing privileged-MFA dependency applies to review actions.
- Only validated category-specific shapes and image-license references are accepted; no HTML rich text rendering, no server-side remote image fetch. Source and license checks still require manual review. Do not present business verification as a guarantee of safety or availability.
- A business can have at most 25 unarchived listings; a listing can have at most 10 image references. Public list pagination limits are enforced.

## API reference

### Public (no login)

```text
GET /api/v1/listings?category=accommodation&q=garden&district=Kandy&limit=24&offset=0
GET /api/v1/listings/{slug}
```

### Vendor (Clerk JWT, organization-scoped)

```text
GET    /api/v1/vendor/organizations/{org_id}/listings
POST   /api/v1/vendor/organizations/{org_id}/listings
GET    /api/v1/vendor/organizations/{org_id}/listings/{listing_id}
PUT    /api/v1/vendor/organizations/{org_id}/listings/{listing_id}
POST   /api/v1/vendor/organizations/{org_id}/listings/{listing_id}/photos
DELETE /api/v1/vendor/organizations/{org_id}/listings/{listing_id}/photos/{photo_id}
POST   /api/v1/vendor/organizations/{org_id}/listings/{listing_id}/submit
POST   /api/v1/vendor/organizations/{org_id}/listings/{listing_id}/archive
```

**Creation example for an accommodation-type organization:**

```json
{
  "title": "Example family guesthouse",
  "summary": "A family-focused guesthouse with independent rooms near the town centre.",
  "description": "Our independently operated guesthouse offers a small selection of rooms. Please contact us directly to confirm child policies, dates, final pricing, accessibility and other needs.",
  "public_email": "info@example.com",
  "public_phone": null,
  "details": {
    "room_types": [{"name":"Family room", "max_adults":2, "max_children":2, "number_of_rooms":3, "indicative_nightly_lkr_minor":1500000}],
    "amenities": ["Wi-Fi"],
    "house_rules": "Please confirm pet policy before arrival."
  }
}
```

Example uses an illustrative business; no real service has been invented or seeded. LKR money is stored as *minor units* (cents); `1500000` means LKR 15,000.00.

### Platform administrator only

```text
GET  /api/v1/admin/listings?status=submitted
GET  /api/v1/admin/listings/{listing_id}
POST /api/v1/admin/listings/{listing_id}/decision
```

Decision body: `{ "decision": "published", "reason": "At least 15 characters explaining independent checks" }` or `"changes_requested"`.

## Apply the changes-only patch (Windows PowerShell)

The previous conflict in `infra/compose.yaml` was caused by the local-only DBeaver port mapping. **This patch does not contain or change `infra/compose.yaml` or `.env`**, so your current PostgreSQL/ClamAV volume settings are retained.

```powershell
cd "D:\My Projects\Tourismo\tourismo_app"
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase4_Part1_Service_Listings_Changes_Only.patch"
git apply --check $patch
# Only if the check succeeds:
git apply $patch

docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
docker compose --env-file .env -f infra/compose.yaml exec app alembic current
docker compose --env-file .env -f infra/compose.yaml exec app alembic heads
```

Both Alembic commands should show `0010_service_listings (head)`. **Do not run `docker compose down -v`**. If the patch check fails, do not force it: compare changed files to any local edits.

## DBeaver checks

```sql
SELECT version_num FROM public.alembic_version;
SELECT status, category, COUNT(*) FROM public.service_listings GROUP BY status, category;
SELECT COUNT(*) FROM public.service_listing_photos;
SELECT decision, COUNT(*) FROM public.service_listing_reviews GROUP BY decision;
SELECT slug, title, category, district FROM public.service_listings WHERE status='published';
```

The new listing tables can be empty immediately after migration: the platform intentionally has no artificial providers or demo listings.

## Acceptance test (two distinct authenticated users)

1. Confirm `/api/v1/listings` returns `[]` if nothing has yet been reviewed; it should respond 200 to guests.
2. Create a vendor organization with a test email account and complete verification from a **different** admin account.
3. With the vendor account, create an accommodation listing including one room type and a public contact, add a correctly credited HTTPS photo, submit for review.
4. Confirm the listing does not appear publicly while `submitted` and that a different vendor account cannot read/edit it.
5. With the independent admin, approve from `/admin/listings`. Check audit/review rows and the new public listing detail page.
6. Archive the listing as the vendor and confirm it disappears from the public search. No booking or payment should be created.
7. Test that a rejected/expired business's listings aren't publicly discoverable, that anonymous admin/vendor API calls receive 401, and that an admin with vendor membership cannot self-approve.

## Verification status

The repository's Python tests run locally without PostgreSQL and include the Phase 4.1 route/schema/ownership checks. PostgreSQL integration tests remain environment-dependent. A full frontend Vite build requires npm dependencies; if npm cannot reach its package registry, the Docker build on your machine is the authoritative check. Real Clerk identity and browser-end-to-end workflows require a configured local instance.
