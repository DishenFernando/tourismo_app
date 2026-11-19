# Tourismo — Phase 3.1 Vendor Registration & Manual Verification

**Base:** Phase 2.5 (`0007_pilot_destination_guides`)
**New migration:** `0008_vendor_onboarding`
**Delivery:** additive changes-only Git patch (no `.env`, Compose, existing migrations or volume reset).

## Features now implemented

1. A Clerk-verified tourist account can create up to five private vendor organizations (`/vendors`), in six categories: accommodation, restaurant, guide, transport, tour operator, and activity.
2. Organization owner and scoped membership rows are separate from platform administrator roles. Owner can invite an **existing** Tourismo account by its local UUID, to a manager or staff role. The invited person must accept. Staff can read scoped organization data; managers can edit applications and add evidence. Only owners invite/revoke team members. No one can invite themselves as owner.
3. Application profile (legal business name, business registration/licensing numbers, contact email/phone, operating address) can be corrected while in draft, changes-requested or rejected state. A submitted or approved application is locked.
4. Registry/license **reference metadata**, including issuer, reference number and optional expiration date, is private and explicitly **not** proof of verification; no binary documents or publicly exposed private addresses.
5. Vendor submits an application with a registration/license reference and at least one unexpired evidence reference. Submitted applications appear in the administrator-only `/admin/vendors` queue.
6. Admin records reason and optional official source for rejection/changes requested, and a mandatory HTTPS source for approval. Review decisions are retained in `vendor_verification_checks`, and important operations in `audit_events`. Admins cannot review organizations they own or belong to, even as a former member.
7. Vendor sees decision and feedback after review and may correct/resubmit an application returned for changes.
8. Tourists still browse destinations and plan trips without login; existing content studio roles, Clerk profile storage and saved trips remain unchanged.

## Deliberately NOT implemented / product gates

- **Secure uploaded verification documents:** file bytes, image scans, evidence storage, presigned private object storage, malware scanning, retention/erasure, and staff-access logging. Only manually entered document/reference metadata exists. Do not claim an applicant has uploaded proof.
- **Official automated verification:** no SLTDA API integration or assumption of source authority. Real staff must check official records outside the app, determine category-specific eligibility, and write an accurate review reason/source. An HTTPS URL alone is not a technical proof of authenticity.
- **MFA/step-up enforcement for owners or financial users:** strongly recommended by the blueprint; not yet enforced in this first slice. Require it before real production verification/finance operations.
- **Public business listings, availability, vendor inquiries, prices, subscription or 30-day trial:** intentionally **not activated**. An approved application has `has_public_listing=false`, `subscription_trial_started=false`. Phase 4 starts category-based listings, and trial timing remains tied to the policy-selected first approved listing trigger.
- **Email invitation delivery:** invitations are internal and only to existing Tourismo user UUIDs. Other users see pending invites in their business dashboard; no external email is sent. Later implement consented email invitations and expiration/revocation policy.
- **Duplicate detection across different registration identifiers, licensing equivalence, formal appeal process, legal data retention and staff case assignment** need production-ready handling.

## Apply on Windows

From your **current** Tourismo repository root (`D:\My Projects\Tourismo\tourismo_app`):

```powershell
cd "D:\My Projects\Tourismo\tourismo_app"
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase3_Part1_Vendor_Onboarding_Changes_Only.patch"
git apply --check $patch
# Only proceed if the command above succeeds silently:
git apply $patch
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
docker compose --env-file .env -f infra/compose.yaml exec app alembic current
docker compose --env-file .env -f infra/compose.yaml exec app alembic heads
```

The last two commands should show **`0008_vendor_onboarding (head)`**. If they still say `0006` or `0007`, see `apps/api/migrations/versions/` and rebuild the application. Do not run `docker compose down -v`.

## UI demo flow

1. Sign in with Google/email and open **For businesses** in the header, or `http://localhost:8000/vendors`.
2. Register a test business with genuine ownership details (avoid using real private business documentation in demonstration environments). Add a license/registration **reference**, including issuer and expiry if available.
3. Submit for review. The application should now be **submitted**, and the form should lock.
4. Sign in with a **different account with platform admin role**; open `http://localhost:8000/admin/vendors`.
5. Independently review source information. Record an approval (with actual source link) or request changes (with a detailed reason). **Do not approve fictitious or unverified businesses.**
6. Return as owner, refresh `/vendors`, and see review state and feedback. If changes requested, correct and resubmit.
7. For staff: the invited user can copy their **Tourismo user ID** from `/account`, share it with the organization owner, and accept the pending invitation on `/vendors`.

### Create your first admin (existing CLI)

Run **only in a trusted operator terminal** after the admin user has signed into Tourismo:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec app `
  python -m tourismo.admin.cli grant --subject user_YOUR_EXACT_CLERK_SUBJECT --role admin --confirm
```

Roles cannot be set via a browser-supplied `role` field. Do not give the same account both applicant ownership and the administrator review role when testing approval; conflict-of-interest safeguards will reject self-review.

## Verify PostgreSQL with DBeaver

```sql
SELECT version_num FROM public.alembic_version;
SELECT id, business_name, category, verification_state, created_at
FROM public.vendor_organizations ORDER BY created_at DESC;
SELECT organization_id, user_id, role, state FROM public.vendor_memberships;
SELECT organization_id, evidence_type, issuer, expires_on FROM public.vendor_evidence;
SELECT organization_id, reviewer_id, decision, checked_at
FROM public.vendor_verification_checks ORDER BY checked_at DESC;
```

Evidence reference numbers and business addresses are private; query these only for authorized administration.

## Test plan

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-phase31.ps1
```

Backend test suite (inside a suitable Python environment):

```powershell
cd apps\api
python -m pytest -q tests
```

The full PostgreSQL integration test requires **a separate disposable, fully migrated test database** specified by `TEST_DATABASE_URL`. **Never aim this test at your existing `tourismo` production/development database**; it inserts and deletes sample users and businesses.

## Changes and data compatibility

- Adds four tables: `vendor_organizations`, `vendor_memberships`, `vendor_evidence`, `vendor_verification_checks`.
- No destructive changes to `users`, trips, destinations, content or editorial tables.
- Backend routes are private except existing public tourist routes.
- Existing `.env`, Docker Compose, DBeaver port mapping, and Clerk keys are untouched.
- Database rollback `0008` would **delete vendor data**; do not downgrade without a backup.

## Phase 3.2 recommendation

Add private evidence upload via a correctly configured object store (signed short-lived uploads/downloads, file size/type scanning, encryption, minimal staff privileges, audit, expiry/retention), enforce step-up MFA for staff/admin, and improve review/appeal/renewal processes before opening registrations to the public. Phase 4 can then introduce actual category-specific public listings with separate review/entitlement gates.
