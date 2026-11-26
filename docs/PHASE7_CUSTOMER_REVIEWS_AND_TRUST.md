# Tourismo Phase 7 — Reviews, Ratings & Trust

**Release status:** Changes-only source update delivered; final Docker, real PostgreSQL migration, Clerk, and browser testing are required on the user's environment.
**Prerequisite:** Phase 6 applied (Phase 5.4 and 5.3 already included); last accepted migration `0015_location_links`.
**New database revision:** `0016_customer_reviews`.

## 1. Product intent

Allow signed-in tourists to write one honest review per real publicly published service listing, see moderated community feedback, flag abuse, and read a business's independently moderated response. **Tourismo has no booking/visit verification**, so neither a review nor a star rating constitutes a verified stay, purchase, or service quality endorsement. Business identity verification, customer ratings, and listing publication are three independent processes.

This first Phase 7 increment covers **service listings**. It does not create reviews of destination editorial articles, users, fictional demo providers, unlisted companies, or unapproved services.

## 2. Permissions and moderation

| Role | Operation | Conditions |
|---|---|---|
| Guest | Read visible approved reviews and average rating | Listing remains eligible/public; authors identified only as “Tourismo traveler” |
| Signed-in tourist | Submit/update feedback | Profile complete, one review per account per listing, not business owner or affiliated member, rating 1–5, content limits |
| Review author | Read own pending/changes-requested record | Identity verified through Clerk JWT |
| Signed-in user | Report a public review | Cannot report own review; one report per account per review |
| Active vendor owner/manager | Propose/modify a provider reply | Review published and listing still public; only own organization; reply remains pending until moderation |
| Vendor staff | Read customer feedback for assigned organization | Cannot post a reply without owner/manager role |
| Admin | Publish, request changes or hide feedback and replies | Independent admin-scoped database role; recent MFA required in production; audit event recorded |
| Admin | Dismiss report or hide reported review | Reason required; audit event recorded |

Rejected/expired provider records are excluded via existing `_public_query()`. A review also disappears publicly if the listing is unpublished/archived. Previously published replies are hidden while a replacement is reviewed. Edited customer reviews likewise disappear until reapproval. Reviews explicitly marked hidden cannot be resubmitted by their author in this version; appeal handling is operational/manual.

### Why reviews are *not* verified visits

Tourismo does not yet process reservations/payments or receive independent confirmation of visits. A registered user is not equivalent to a paying or confirmed customer. The UI states **“Visit not verified.”** Businesses cannot self-rate through their owner or current/pending member accounts. Stronger fraud detection is future work.

## 3. Data model

Migration `0016_customer_reviews` adds **three tables only**:

- `customer_reviews`: UUID, listing FK, author FK, 1–5 rating, short title, body, moderation status, reason, moderator, timestamps. Unique `(listing_id, author_id)`.
- `customer_review_replies`: one response per review (FK/PK), organization/author FK, body, moderation state, timestamps.
- `customer_review_reports`: UUID, review FK, reporting-user FK, reason, explanation, open/dismissed/actioned status, admin decision and timestamps. Unique `(review_id, reporter_id)`.

Existing `service_listing_reviews` remains an **independent editorial listing-approval** table and is not replaced or renamed. Existing `audit_events` tracks moderation and reporting. No existing table or record is deleted by the upgrade.

## 4. Public and privileged API

Base URL `http://localhost:8000/api/v1`.

| Method | Endpoint | Access |
|---|---|---|
| GET | `/reviews/listings/{slug}` | Public, only for eligible published listings; rating average from approved reviews |
| GET | `/reviews/listings/{slug}/mine` | Signed in; only author's own submission |
| POST | `/reviews/listings/{slug}` | Signed in, complete profile, non-affiliated author |
| POST | `/reviews/{review_id}/reports` | Signed in, reporter not author |
| GET | `/vendor/organizations/{org_id}/customer-reviews` | Active team member |
| POST | `/vendor/organizations/{org_id}/customer-reviews/{review_id}/response` | Owner/manager |
| GET | `/admin/customer-reviews?state=pending` | Admin |
| POST | `/admin/customer-reviews/{id}/decision` | Admin + MFA in production |
| GET | `/admin/customer-reviews/replies?state=pending` | Admin |
| POST | `/admin/customer-reviews/replies/{id}/decision` | Admin + MFA in production |
| GET | `/admin/customer-reviews/reports?state=open` | Admin |
| POST | `/admin/customer-reviews/reports/{id}/decision` | Admin + MFA in production |

**Public response projection** never includes user IDs, email addresses, private moderation notes, evidence documents, reporter information, or unapproved responses. Query result sizes are bounded. Guest requests are subjected to the existing per-process limiter (shared edge/Redis limiting remains a production requirement).

## 5. Frontend pages

- `/listings/{slug}` — reviewed customer feedback, average stars, review composer (requires profile), public provider replies, abuse report form. Fictional `/demo/listings/{slug}` does **not** include reviews.
- `/vendor/feedback` — choose your business, see its approved reviews and reply status, submit moderated replies.
- `/admin/customer-reviews` — separate admin queues for customer reviews, provider replies and abuse reports; mandatory moderation reason.

The existing Admin Content Studio, listing/publication review, provider verification, location-link, mapping, saved-trip and budget flows are unchanged.

## 6. Installation (Windows PowerShell)

Before changing code, **back up the database**:

```powershell
cd D:\Tourismo\Tourismo
$dbContainer = docker compose --env-file .env -f infra/compose.yaml ps -q db
$backup = "tourismo-before-phase7-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
docker compose --env-file .env -f infra/compose.yaml exec -T db pg_dump -U tourismo -d tourismo -Fc -f /tmp/tourismo-before-phase7.dump
if ($LASTEXITCODE -ne 0) { throw 'Backup creation failed' }
docker cp "${dbContainer}:/tmp/tourismo-before-phase7.dump" ".\$backup"
if ($LASTEXITCODE -ne 0) { throw 'Backup export failed' }
```

Then obtain the Phase 7 Git patch from the release pack:

```powershell
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase7_Customer_Reviews_Changes_Only.patch"
git apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Stop: Phase 7 patch conflict, do not apply' }
git apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Stop: Phase 7 patch apply failure' }
docker compose --env-file .env -f infra/compose.yaml up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed' }
docker compose --env-file .env -f infra/compose.yaml ps
```

The application startup invokes Alembic and upgrades to `0016_customer_reviews` if the build succeeds. Verify:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec -T db psql -U tourismo -d tourismo -At -c "SELECT version_num FROM public.alembic_version;"
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase7.ps1
```

Expected migration: `0016_customer_reviews`. **Do not run `docker compose down -v`, reapply earlier patches, or overwrite your customized `infra/compose.yaml`.**

The old phase verifiers that hardcode migration `0015_location_links` are historical and will fail once Phase 7 migrates. The new Phase 7 verifier performs fresh read-only checks instead of chaining these old scripts.

## 7. Acceptance scenarios

1. Confirm Phase 6 saved-trip edit and map still work.
2. Guest opens a published real service and sees an empty or approved review summary, never private draft content.
3. Sign in with an incomplete profile: posting is blocked. Complete the profile, submit a 4-star review: status **pending**, no immediate public star count change.
4. Admin opens `/admin/customer-reviews`, reviews content, enters a reason, publishes. Guest refresh now sees 4/5 rating and anonymized comment.
5. Reviewer edits their approved review: it returns to **pending** and temporarily disappears publicly until another approval.
6. Business owner or active/pending member tries posting a review for their own business: HTTP 403.
7. Vendor owner/manager writes a response: it is **pending**, not public. Admin approves; guest sees it.
8. Signed-in user reports abusive feedback. Admin dismisses or hides reported review with a reason. Hide removes review from public summary and hides its provider reply.
9. Unverified business with approved listing: feedback works and stars show, but **no verified business badge** appears. Rejected/expired organizations remain nonpublic.
10. No review section appears for fictional demo listings. Test mobile sizes, empty queues, role restrictions and no user/email leakage.

## 8. Tests and limitations

- Backend unit/contract/security regression suite: see release README for exact run.
- Migration: PostgreSQL offline SQL generation verified; actual migration against the user's live database still required.
- Frontend: syntax parsing checked; **full Vite/TypeScript compilation on the user's Docker build is required** because npm registry access was unavailable in this environment.
- Five existing live-PostgreSQL integration tests are skipped without a database; they must run against a controlled test environment before production.

**Future hardening:** shared distributed rate limits, review-appeal workflow, abuse detection, removal/redaction requests, editorial evidence retention policy, moderation SLAs, notification delivery, accessibility audit, and compliance/privacy legal review. No booking or payment claims should be added without independent verification mechanisms.
