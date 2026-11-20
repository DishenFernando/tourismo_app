# TOURISMO — Phase 4.1 fictional demo data pack

**Purpose:** populate a *local development database* with plausible-looking, completely **fictional** providers to exercise all six structured listing types and the vendor UI without falsely approving any business.

**Requires:** `0010_service_listings` migration, current Phase 4.1 code, PostgreSQL and two existing Clerk-backed Tourismo user rows.

**Sample scope:** 12 organizations, 24 listings (4 in each of 6 categories), 4 unlinked sample user profile records, and 2 unchanged existing real user accounts used as owners of two test organizations each. All `vendor_organizations.verification_state` and `service_listings.status` values remain `draft`. No evidence, documents, real contacts, image rights, review records, platform admin roles, or published status is invented.

The SQL data file is provided **separately** from the Git patch, because it includes the two user UUIDs/Clerk subjects supplied by the project owner. **Do not commit or publish this user-specific SQL file** or use it against production.

## Installation (Windows PowerShell)

1. Take a database backup. Example: `docker compose --env-file .env -f infra/compose.yaml exec -T db pg_dump -U tourismo -d tourismo -Fc > tourismo-before-demo.dump` (PowerShell 7 recommended for binary redirection; use DBeaver Backup or an explicit file stream if on older PowerShell).
2. Confirm `docker compose --env-file .env -f infra/compose.yaml exec app alembic current` shows `0010_service_listings`.
3. Download and check the companion *changes-only* `.patch`, then `git apply` it. This patch leaves `.env`, `infra/compose.yaml` and existing migrations unchanged.
4. Add `APP_ENVIRONMENT=development` and `ENABLE_DEMO_CATALOG=true` to the root `.env` (keep existing Clerk/database settings).
5. Rebuild: `docker compose --env-file .env -f infra/compose.yaml up --build -d`.
6. Open the **standalone** `Tourismo_Phase41_Fictional_Demo_Seed.sql` in DBeaver. Choose **Execute SQL Script** (rather than executing only a selected statement) against `tourismo/public`. It is a single transaction: if your two real users cannot be found, PostgreSQL raises an error before inserting anything.
7. Check `http://localhost:8000/demo/listings` and `/api/v1/demo/status`. All 24 examples should appear with prominent fictional/demo labels.
8. The unchanged `/listings` route continues to show **only genuinely approved organizations with separately published listings**. These demo records do not appear in the real directory.

### If you prefer running the SQL from PowerShell

Copy the downloaded SQL into your Tourismo project directory, then:

```powershell
cd "D:\My Projects\Tourismo\tourismo_app"
Get-Content -Raw .\Tourismo_Phase41_Fictional_Demo_Seed.sql |
  docker compose --env-file .env -f infra/compose.yaml exec -T db `
    psql -v ON_ERROR_STOP=1 -U tourismo -d tourismo
```

On some Windows terminals, PostgreSQL error exit codes can be hidden by pipeline behavior; check the output and run the verification queries below.

## Accounts and authentication rules

- Two existing Clerk-backed account rows are **read-only** to this seed. It checks their exact identities and associates each with two new fictional vendor organizations. Their names, profiles, passwords, sessions and platform roles are not modified.
- Four inserted rows have `auth_subject` beginning `tourismo_demo_unlinked:` and `status='demo_unlinked'`. They are **placeholder database records, not actual Clerk accounts**, cannot sign in, and must not be used for authentication or admin permissions.
- To test additional actual user sessions, create real separate test users in your Clerk development instance, sign them in once, and use the normal vendor onboarding/team-invitation workflows.

## Security and review design

- `ENABLE_DEMO_CATALOG=false` by default. Both the opt-in flag and `APP_ENVIRONMENT=development` are required; in production the demo API responds `404` even if the flag is accidentally set.
- `/api/v1/demo/listings` and `/api/v1/demo/listings/{slug}` use narrow data filters (`tourismo-demo-` slugs, `[DEMO]` business-name prefix, both draft statuses); return only the existing *public listing field allowlist*, remove all contact fields, and add a fictional-data disclaimer.
- The ordinary `/api/v1/listings` query remains unchanged and enforces published listing, approved organization, and no expired evidence.
- No published status or admin verification approval is seeded; no fake government licenses or certificates are inserted; no unlicensed photos are linked; money amounts are invented LKR minor-unit samples.
- Although the demo API is disabled in production, **do not deploy a development database containing these test records**. Use a separate clean production database and real review processes.

## Database verification (DBeaver)

```sql
SELECT version_num FROM public.alembic_version;
SELECT category, COUNT(*) AS listings FROM public.service_listings
WHERE slug LIKE 'tourismo-demo-%' GROUP BY category ORDER BY category;
SELECT business_name, category, district, verification_state
FROM public.vendor_organizations WHERE business_name LIKE '[DEMO] %'
ORDER BY category,business_name;
SELECT title, status FROM public.service_listings
WHERE slug LIKE 'tourismo-demo-%' ORDER BY category,title;
SELECT display_name, auth_subject, status FROM public.users
WHERE auth_subject LIKE 'tourismo_demo_unlinked:%' ORDER BY display_name;
SELECT COUNT(*) AS accidentally_published_demos FROM public.service_listings
WHERE slug LIKE 'tourismo-demo-%' AND status='published';
```

**Expected:** 4 listings in each category; 12 businesses; 4 unlinked users; 0 accidentally published demo listings. Re-running the seed does not duplicate records (stable UUID identifiers and `ON CONFLICT DO NOTHING`).

## Demo content examples

- Accommodation: Kandy Garden Stay and Galle Courtyard Stay; room types, family occupancy, sample nightly estimates.
- Restaurants: Ella Spice Table and Colombo Heritage Cafe; fictional menu items, cuisine and dietary filters.
- Guides: Anuradhapura Heritage Guide and Sigiriya Trails Guide; languages, service regions and indicative daily rates.
- Transport: Kandy Transfer Vans and Galle Coast Rides; cars/vans, seats and luggage counts.
- Tour operators: Island Culture Tours and Hill Country Excursions; duration, areas and minimum ages.
- Activities: Bentota River Experiences and Ella Nature Walks; illustrative experiences, regions and prices.

**Limitations:** Demo images remain placeholders because the fictional providers have no genuine property photos or rights documentation. Public booking, payment and real-time availability are not implemented. No new Alembic migration is needed because only existing Phase 4.1 tables are populated. Full Docker/Clerk/PostgreSQL end-to-end validation must be performed locally.
