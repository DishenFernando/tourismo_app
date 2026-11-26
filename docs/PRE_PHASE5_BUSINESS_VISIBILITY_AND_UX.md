# TOURISMO — Pre-Phase-5 Product & Trust Model Review

**20 November 2026 · Incremental UX/policy change atop Phase 4.5 Part 2 · Local implementation**

## Executive decision

Tourismo separates **joining the platform**, **business identity/authorization review**, and **approval of a particular public listing**.

- An authenticated tourist may create a private business draft with category, business name and email.
- A business may prepare and submit a completed listing for content review **before Tourismo has verified the business**.
- Only an independent platform admin can publish the listing. The admin must check claims, applicable permit obligations, and photo rights. Unverified businesses do not get a "Verified" badge.
- A business receives the **Verified business** badge only if the server has `verification_state = 'approved'` with no expired evidence. This does not certify quality, safety, prices, accessibility, or availability.
- Rejected businesses or businesses in `expired_license` state cannot publish new listings or appear in public discovery. An expired reference blocks publication/visibility even if background expiry maintenance has not run.
- The existing development-only fictional demo catalog stays separate. Its records remain private/drafts and are *never* represented as verified businesses.
- Current release does **not** provide online tourist booking, payment, platform-verified availability, or provider identity guarantees for unverified businesses.

### Explicit legal/reputational boundary

Publicly listing an unverified tourism provider does **not** imply they may lawfully operate. Some tourism businesses and professionals may need SLTDA or other applicable permits/registration. Tourismo must maintain category-specific compliance criteria, legal review, incident-reporting/suspension capabilities, and policy enforcement before a public launch. See [SLTDA Registration Portal](https://eservices.sltda.gov.lk/ApplicationMain.aspx?Type=D) and [SLTDA Register With Us](https://sltda.gov.lk/en/register-with-us). These are external requirements; this local development increment does not perform automatic regulatory checks or implement regulator-supplied certification.

## Permission/visibility matrix

| Business state | Owner can draft listing | Submit completed listing | Admin can publish listing | Public result after admin approval | Verified badge |
|---|---:|---:|---:|---:|---:|
| `draft` | Yes | Yes (complete location and listing required) | Yes, after claim/permit review | Yes | No |
| `submitted` | Yes | Yes | Yes, separate listing review | Yes | No |
| `changes_requested` | Yes | Yes | Yes, separate listing review | Yes | No |
| `approved` with current evidence | Yes | Yes | Yes | Yes | **Yes** |
| `approved` but expired evidence | Yes, private | **No** | **No** | **No** | No |
| `expired_license` | Yes, private | **No** | **No** | **No** | No |
| `rejected` | Yes, private | **No** | **No** | **No** | No |
| Fictional `[DEMO]` | Development sample | Never through real workflow | Never represent as real | Dedicated demo preview only | Never |

**Independent listing moderation is mandatory in every allowed state.** This release does *not* auto-publish unverified businesses, remove admin review, or allow owners to choose the badge.

## Why this differs from Phase 4.5

The old `listings/routes.py` enforced `VendorOrganization.verification_state == 'approved'` both at listing submission/publication and in the public query. A complete but unverified listing could not reach visitors even after separate content review. The front-end had disabled **Submit** buttons until verification.

### Implemented changes

1. Backend now uses `_publishable_org` (eligibility and evidence-expiry checks) for listing submission and listing/revision review. Identity verification remains separate.
2. Public search and individual listings return only `ServiceListing.status == 'published'`, exclude rejected and expired-license organizations, and enforce current evidence expiry independently of background jobs.
3. `business_verified` and `business_name` are server-derived response fields; no public owner UUIDs, document details, registration numbers, or private review feedback are added.
4. Public cards render a verified badge **only** when the server says true. Unverified cards show no verification badge. The detail page gives a neutral factual statement explaining that business verification is incomplete.
5. Vendor listing screen allows eligible unverified organizations to submit completed listings for content review. Organization location and all existing listing fields still must validate.
6. Business dashboard distinguishes "join/list a service" from "apply for the verified badge".
7. Destination editor now asks primarily for **name and district**, derives province, suggests slugs, lets editors save an initial guide draft before adding references, and retains controlled, sourced review/publication. AI-generated illustrations remain disclosed as illustrations, not real place photographs.

No new database migration is required. The existing `0014_vendor_experience` schema already supports these states and review stages.

## UX & security audit — 22 findings

| Area | Finding | Treatment |
|---|---|---|
| Joining | Licensing-first feels like a barrier | **Now:** business draft and listing review independent of verified badge |
| Public trust | "Published" mistaken for "Verified" | **Now:** badge is separate; detail-page statement for unverified |
| Badges | Vendors could fake badges in descriptions or photographs | **Policy next:** content moderation / brand misrepresentation rules |
| Business suspension | Rejection and expired status need suppression | **Now:** fail-closed; **next:** dedicated `suspended` state and appeals |
| Regulated categories | Legally necessary permits vary by provider | **Before public beta:** counsel-reviewed category rules and checks |
| Expired documents | Maintenance jobs may not run | **Now:** query-time expiry checks, not job-only checks |
| Demodata | Fictional examples could look real | **Preserved:** separate demo API and prominent labels |
| Destination creation | Manually input name, slug, district, province | **Now:** district selection + derived province + suggested slug |
| Guide sources | Sources required too early visually | **Now:** advanced disclosure while keeping source-before-publication |
| Attraction slug | Technical slug cumbersome | **Now:** suggestion based on attraction name |
| Images | Editors managing license URLs by hand | Already addressed in Phase 4.4 (owned/AI/Commons uploads) |
| AI images | Fictional photo might imply real location | Existing disclosure in discovery and destination pages |
| Vendor media | Remote URLs/licensing difficult | Phase 4.5 Part 2 local upload; production cloud media still pending |
| Vendor docs | Separate license/document forms | Phase 4.5 Part 2 guided attachment flow |
| Vendor team | Raw UUID invite friction | In-app verified-email invitations; outbound mail pending |
| Tourists | Services cannot yet be attached to itineraries | Later trip-service integration |
| Search | No interactive map pins or routing | Phase 5 |
| Content depth | Many destination records lack full guides | Editor quality audit remains necessary |
| Translations | Sinhala/Tamil limited | Human-reviewed localization workflow pending |
| Vendor ranking | Verified vendors may unfairly dominate | Show verification only as factual badge; design search ranking policy separately |
| Fraud response | No mature reports/takedown/appeal | **High priority before public beta** |
| Production | Uploads/local image BLOBs are dev-only | Cloud storage, moderation, backups and retention before public beta |

## Suggested minimum viable trust policy before launch

- Clear rules: *listed ≠ verified; verification ≠ recommendation; no booking guarantee*.
- Admin-reviewed service profile required for all public listings.
- Strong report/takedown mechanism and audit trail for impersonation, illegal services, unsafe accommodation/transport, fake imagery, and misleading prices.
- Clear legal checklist per provider type (e.g. guide/driver/accommodation/tour operator).
- Verified badge criteria published in Help Center, including what was checked, last review date, expiry, renewal and revocation handling.
- Rate limits per account/IP, duplicate-business detection, media moderation and business-contact verification.
- Platform-admin roles assigned by trusted CLI, with MFA in production; no vendor self-approval.
- Automated verification-expiry process and emergency unpublish controls.
- A safe contact-exchange experience without payment escrow until bookings are implemented.

## Release/installation

1. Apply `Tourismo_Pre_Phase5_Visibility_UX_Changes_Only.patch` to the **Phase 4.5 Part 2 source**, including the separately corrected unused import in `Vendors.tsx`.
2. Inspect `git apply --check` output **before** applying. If it fails, do not force it.
3. Build with `docker compose --env-file .env -f infra/compose.yaml up --build -d`.
4. Confirm `0014_vendor_experience` in `alembic_version`. No migration should advance beyond that because this is a code-only increment.
5. Log into a normal Clerk account, create an unverified business draft with location, create/complete a listing, submit it for content approval, and let an **independent** admin approve it.
6. Confirm public listing appears *without* a verified badge. Independently verify business through normal admin flow, refresh listing and confirm badge appears. Do not manipulate verification status directly in a shared database.
7. Check a rejected/expired test business does not show in public results.
8. Use `scripts/verify-pre-phase5.ps1` for read-only infrastructure, version and privacy checks.

**Validation here:** Python test suite passed 115, skipped 5 PostgreSQL-dependent integration tests; TSX syntax parsed. Full Vite/Docker and end-to-end real PostGIS/Clerk behavior still require your local test.
