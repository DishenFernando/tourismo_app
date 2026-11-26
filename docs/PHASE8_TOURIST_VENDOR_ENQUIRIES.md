# TOURISMO — Phase 8: Tourist–Vendor Enquiries

**Source release date:** 23 November 2026
**Status:** Source implementation, regression tests, and offline migration SQL checked; live PostgreSQL, Clerk, Docker frontend build, and browser acceptance pending.
**Requires:** Phase 7.1 source and live revision `0017_review_media` before installation.
**New database revision:** `0018_service_enquiries`.

## Purpose

Allow a traveler to ask a **real independently published provider** for service information, indicative availability or a quotation without representing Tourismo as a booking or payment system. The public listing's independent content review and the organization's verification status remain separate from messages and provider statements. Quotes and responses are **not** Tourismo-guaranteed prices, inventory, availability, or reservations.

### User journeys

1. A guest views real service listings and their public provider contact fields without signing in. Guests cannot send or read in-app enquiries.
2. A logged-in traveler completes their profile and opens a real `/listings/{slug}` page, sends a subject and first message, and lands in `/enquiries`.
3. An active owner/manager opens `/vendor/enquiries`, selects their organization and replies. The traveler reads and responds in their own `/enquiries` inbox.
4. The traveler may withdraw their enquiry; an owner/manager may close it. Closed/withdrawn/blocked conversations cannot be replied to. A new enquiry can be created after the prior one closes.
5. Either participant can report the conversation. An admin opens `/admin/enquiry-reports`, inspects private message evidence (recent MFA in production), dismisses an invalid report or blocks the conversation with a recorded reason.

### Authorization/privacy boundaries

| Capability | Access |
|---|---|
| Browse listing / public contact fields | Guest, as in Phase 7 |
| Create enquiry | Signed-in traveler with completed profile, eligible real published listing, not an affiliated owner/member |
| List/read/reply/withdraw own enquiry | That traveler's verified server-side user ID only |
| Vendor list/read/reply/close | Active **owner or manager** of the organization owning the listing; staff cannot access this inbox |
| Submit private abuse report | Traveler or active owner/manager participant |
| Inspect reports, private messages, moderate | Platform admin; recent MFA for private thread evidence and decisions in production |

Public APIs expose **zero** enquiry messages; all conversation APIs require authentication. Responses omit private email addresses, phone numbers, Clerk subjects, sender user IDs and provider documents. React renders message text as escaped text, not injected HTML. The `/demo/listings/` fictional catalog cannot receive enquiries. Nonpublic or expired/rejected providers cannot receive new enquiries; if a listing later becomes nonpublic, the provider cannot send new messages through it.

### Data model

`0018_service_enquiries` adds **three tables only**, with no existing rows modified or dropped:

- `service_enquiries`: UUID, listing FK, traveler FK, subject, lifecycle state and timestamps. Partial unique index permits one active enquiry per traveler/listing.
- `service_enquiry_messages`: immutable conversation entries containing sender ID, **server-assigned** sender type, message body and timestamp. Indexed for latest-message pagination and per-sender rate checks.
- `service_enquiry_reports`: reporter, reason, explanation, review decision, state and timestamps. One report per reporter/thread.

States: `open`, `answered`, `closed`, `withdrawn`, `blocked`. These **never mean booking confirmed**. Existing reviews, approvals, vendor verification, destinations, trips, and budgets are untouched. Changes to these records are also reflected in `audit_events` without storing message content in that shared log.

### API

Base `/api/v1`:

| Method | Endpoint | Access |
|---|---|---|
| POST | `/enquiries/listings/{slug}` | Completed-profile traveler |
| GET | `/enquiries` | Current traveler only |
| GET | `/enquiries/{id}?offset=0&limit=50` | Current traveler only |
| POST | `/enquiries/{id}/messages` | Current traveler, active thread |
| POST | `/enquiries/{id}/withdraw` | Current traveler, active thread |
| POST | `/enquiries/{id}/reports` | Traveler or vendor participant |
| GET | `/vendor/organizations/{org_id}/enquiries` | Owner/manager |
| GET | `/vendor/organizations/{org_id}/enquiries/{id}` | Owner/manager |
| POST | `/vendor/organizations/{org_id}/enquiries/{id}/messages` | Owner/manager, public listing |
| POST | `/vendor/organizations/{org_id}/enquiries/{id}/close` | Owner/manager |
| GET | `/admin/enquiry-reports?state=open` | Admin |
| GET | `/admin/enquiry-reports/{report_id}/thread` | Admin + production MFA |
| POST | `/admin/enquiry-reports/{report_id}/decision` | Admin + production MFA |

Input length limits: subject 8–140, new enquiry 20–2000, additional message 10–2000, report explanation 20–600 characters. Unknown JSON fields are rejected. Enquiry creation is limited to **8 in a rolling 24 hours per user**; 1 active thread per traveler/listing enforced by PostgreSQL; messages limited to **40 per hour per user**. These DB-backed checks are a first layer; distributed shared edge rate limits and more advanced abuse mitigation remain a production gate. Pagination caps: 50 inbox rows (max offset 1000); 50 conversation messages by default (100 max, offset 10000). The app offers a way to load older messages.

### Not implemented in this increment

- Booking acceptance, inventory commitments, payment/escrow, deposits, or Tourismo pricing guarantees.
- Outbound email/SMS/WhatsApp notifications or email notification consent. Users check their in-app inboxes manually. A future provider-neutral outbox must be introduced **only** with opt-in, delivery retries and an approved provider.
- File attachments, PII extraction or automated content scanning. Do **not** exchange ID cards, payment cards or other sensitive information in messages.
- A production-enforced retention/erasure timeline, privacy/legal sign-off, automation for moderation SLAs, provider blocking, spam scoring, and shared rate limiting.

### Deployment / installation — Windows PowerShell

Run at `D:\Tourismo\Tourismo` with Phase 7.1 already deployed, verified and backed up:

```powershell
cd D:\Tourismo\Tourismo
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase7.ps1
```

**Before applying anything**, back up PostgreSQL:

```powershell
$dbContainer = docker compose --env-file .env -f infra/compose.yaml ps -q db
if (-not $dbContainer) { throw 'Database container is not running' }
$backup = "tourismo-before-phase8-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
docker compose --env-file .env -f infra/compose.yaml exec -T db `
  pg_dump -U tourismo -d tourismo -Fc -f /tmp/tourismo-before-phase8.dump
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
docker cp "${dbContainer}:/tmp/tourismo-before-phase8.dump" ".\$backup"
if ($LASTEXITCODE -ne 0) { throw 'Backup export failed' }
```

Place `Tourismo_Phase8_Enquiries_Changes_Only.patch` in Downloads, and check your repo has no overlapping local edits:

```powershell
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase8_Enquiries_Changes_Only.patch"
git status --short
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch conflict; stop, do not overwrite files' }
git apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed' }
docker compose --env-file .env -f infra/compose.yaml up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed; inspect build output' }
docker compose --env-file .env -f infra/compose.yaml ps
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase8.ps1
```

Expected revision: `0018_service_enquiries`. The existing Docker startup runs Alembic automatically. **Do not use `docker compose down -v`, overwrite `.env`/`infra/compose.yaml`, apply older patches again, or downgrade by dropping Phase 8 tables.** Do not apply both the Git patch and update-only ZIP. The downgrade in migration code is **destructive to Phase 8 messages/reports** and should not be used as a routine rollback.

### Browser acceptance — required before Phase 9

1. Confirm guest browsing and that a fictional demo listing never shows an enquiry action.
2. Traveler A submits a message to a published real service; check status is `open`. Incomplete-profile account must be blocked.
3. Traveler B cannot see A's enquiry, even by using A's direct UUID. Service provider B cannot read provider A's enquiry even if they guess the UUID.
4. Owner/manager replies to the correct business; traveler sees reply and status `answered`. Staff must get 404 on the vendor inbox.
5. Traveler replies, withdraws and can no longer post. Provider closes another conversation and it no longer accepts replies.
6. Traveler reports an abusive conversation. Admin can view the private evidence and block; both parties lose send permission. Nonadmins cannot see reports or private evidence.
7. Verify separate customer review moderation, vendor verification, map zoom, nearby discovery, saved-trip editing, budget totals, and mobile screen widths still work.
8. Run local Docker and full Vite TypeScript build and complete Clerk login, PostgreSQL migration, user-isolation browser tests. No actual outbound notifications exist.

### Source testing

The uploaded Phase 7 baseline was used unchanged. Backend test suite and TypeScript syntax parsing were run against this Phase 8 working copy. Full npm registry dependency installation, production Vite compile, live database migration and browser acceptance were not available in the current execution environment, so source delivery is **not** production sign-off.
