# TOURISMO — Complete Feature Walkthrough & Demo Scripts

**As-built operating handbook for Phase 0–4.5 Part 2 plus the pre-Phase-5 visibility/UX update · 20 November 2026**

This file is intended for project owners, QA engineers, demo presenters, editors, administrators and potential tourism vendors. It describes **what a user actually clicks, what the backend does, and what successful behavior looks like**. It is not a claim that Tourismo has already been publicly deployed. User-interface wording may vary slightly depending on the current build; the URLs and backend concepts below are drawn from the current application source.

## 0. Test setup: who plays each role?

Use separate genuine **Clerk development** accounts (Google or email OTP):

- **Tourist A** — ordinary signed-in user; can also create a vendor organization.
- **Tourist B** — independent user; use for private-data boundary tests and invitations.
- **Editor** — an existing Clerk account granted only the `editor` platform role by a trusted operator.
- **Admin** — a separate Clerk account granted the `admin` role by a trusted operator; **must not own or belong to the vendor being reviewed**.

A normal user cannot self-assign a platform role. For a local test environment, grant a role using the existing trusted operator command (replace the subject with that account's real `auth_subject` from the `public.users` table):

```powershell
# Do not expose passwords or Clerk tokens in screenshots.
docker compose --env-file .env -f infra/compose.yaml exec app `
  python -m tourismo.admin.cli grant `
  --subject user_REPLACE_WITH_REAL_CLERK_SUBJECT `
  --role admin --confirm
```

Use a different test account for the business owner; do not give the owner admin permissions. Four fictional demo profiles do not have working Clerk authentication.

## 1. Guest: visit Tourismo without signing in

**Scenario G01 — Discover a destination**

**Presenter script:** “I have never used Tourismo before. I should be able to discover Sri Lanka without creating an account.”

1. Open `http://localhost:8000` in a private browser window.
2. Click **Discover**, or open `/discover`.
3. Search for `Kandy`, `Ella`, `Galle`, `Sigiriya` or `Nuwara Eliya`.
4. Choose a destination and read its guide, attractions and tips.
5. Open a credited photograph or the available source/map link.

**Expected:** No authentication prompt; only available/sample-published travel content appears. AI illustrations must be labeled clearly. An editorial sample is not presented as independently verified fact.

**Scenario G02 — Compare regional tourism services**

1. Open `/listings`.
2. Select **Accommodation**, **Restaurants**, **Transport** or another category.
3. Select a destination or province, optionally enter a district.
4. Open one of the published listings.
5. Observe provider details, indicative prices, photos and any contact links.

**Expected:** Only independently approved listings appear. **Verified business** badge appears only for approved/currently verified organizations. Unverified businesses receive **no badge**; the detail page explains that their business verification has not been completed. Published does not mean legal authorization or guaranteed availability. The normal directory may initially be empty until real listings have passed review.

**Scenario G03 — Search by nearby location**

1. At `/listings`, enter a latitude and longitude and choose a radius (up to 100 km), or explicitly permit browser location access.
2. Click **Search** and optionally sort by distance.
3. Inspect the returned listings.

**Expected:** Location is not silently collected. Only published listings with sourced coordinates match radius search. Distances are straight-line, not driving time; no routing/real-time transport is implied. If there are no such records, an empty result is valid.

**Scenario G04 — Family suitability before contacting an accommodation**

1. Choose category **Accommodation**.
2. Enter 2 adults, children aged 5 and 12.
3. Search, open a result, and use the room-suitability checker.
4. Compare the per-room age and maximum-guest policies.

**Expected:** The UI evaluates recorded maximum adults, children, total guests and child-age rules. It does **not** check live room inventory, confirmed price or reservations.

**Scenario G05 — Trip planning without an account**

1. Open `/plan` while logged out.
2. Choose a destination and travel dates; enter group information including children's ages.
3. Add days/stops and budget categories such as transport, dining and accommodation.
4. Enter your own indicative LKR amounts and inspect estimated totals.
5. Print the plan if needed.

**Expected:** Works locally as a guest. No external price feed, actual booking or confirmed quotation is involved.

**Scenario G06 — Save a guest trip after signing in**

1. Prepare a draft trip while logged out.
2. Select **Save across devices**.
3. Authenticate with Clerk using Google or email OTP.
4. Confirm the save when prompted, then open `/saved`.

**Expected:** The browser draft survives authentication and becomes a private trip associated with the Clerk-backed Tourismo account. Signing in alone should not silently publish a trip or charge money.

## 2. Registered tourist and personal account

**Scenario T01 — Sign up using Google**

1. Click **Log in** and **Continue with Google**.
2. Choose a real Google account in Clerk's development flow.
3. Complete sign-in, open `/account` and view the header avatar/profile menu.
4. Edit display name and language; save.

**Expected:** Clerk manages the sign-in; Tourismo creates/reuses one `public.users` row with `auth_subject`. Profile changes save only to the owner's account. Google login is not a vendor-verification process.

**Scenario T02 — Sign up using email OTP**

1. Sign out and open a new session with another valid email account.
2. Enter the address, request the actual Clerk email code and submit it.
3. Open `/account` and save a name/region.

**Expected:** A distinct Clerk identity has its own database profile. Do not create synthetic Clerk subjects directly in PostgreSQL to simulate login.

**Scenario T03 — Edit profile / security settings**

1. Open avatar menu → **My Profile** (`/account`).
2. Update display name, preferred language, region and bio.
3. Save, refresh and verify changes persist.
4. Use Clerk-provided security/account management where available.

**Expected:** A user cannot change their `auth_subject`, assign platform roles, make themselves verified, or edit someone else's profile using this screen.

**Scenario T04 — Saved trip isolation**

1. Log in as Tourist A; create and save a new trip.
2. Copy its display URL / ID (if exposed) and log out.
3. Sign in as Tourist B; open `/saved` and attempt to access Tourist A's trip.

**Expected:** Tourist B cannot view or modify A's private trip. Guests receive 401 from protected trip endpoints. This is an important end-to-end security test.

## 3. Vendor owner: a simpler first-use journey

**Scenario V01 — Join Tourismo without verification first**

**Presenter script:** “I run a small guesthouse. I want to try Tourismo before spending time gathering my license paperwork.”

1. Sign in as Tourist A.
2. Click **For businesses** or open `/vendors`.
3. Create a new organization draft. Choose `Accommodation`, enter a business name and contact email.
4. Save and view the organization's draft profile.

**Expected:** A private record is created; no verified badge and no public listing are created automatically. This account is still a tourist profile and now also a vendor owner.

**Scenario V02 — Complete basic business location**

1. In `/vendors`, select the organization and open **Business details**.
2. Choose a district from the dropdown. Province auto-fills.
3. Add a real operating address and relevant business contact details.
4. Save.

**Expected:** A simple draft can progress. Basic location is required before submitting a listing; proof of verification is **not** required solely to request listing-content review. Business claims remain vendor supplied.

**Scenario V03 — Create a title-only service draft**

1. Open `/vendor/listings`.
2. Select the business and choose **New listing**.
3. Enter a clear title, e.g. `Garden Room` (no fictitious public offer).
4. Save a starter draft and return later.

**Expected:** Draft remains private, not approved or publicly discoverable. No verified badge, no subscription and no booking is created.

**Scenario V04 — Complete the four-step guided listing**

1. Reopen that draft in `/vendor/listings`.
2. Step 1: enter a concise title, introduction and description.
3. Step 2: supply category-specific details, e.g. room capacity/child policy or menu/transport seats.
4. Step 3: add service contact information and optional sourced location coordinates.
5. Step 4: preview, fix validation issues and save.

**Expected:** All required fields validate server-side. Unverified and verified owners use the **same** form. Incomplete title-only drafts cannot be submitted for publication.

**Scenario V05 — Submit a listing while business verification is incomplete**

**This is the key new workflow.**

1. Create an unverified `draft` business (V01), complete district/province (V02), and complete a listing (V04).
2. Click **Submit for publishing review**.
3. Open `/admin/listings` as a *separate* platform administrator.
4. Inspect listing claims, relevant legal permits, images and contact details.
5. Approve and publish only if policy/compliance checks are satisfied.
6. Visit `/listings` as a guest and open that listing.

**Expected:** The listing may appear publicly, but **no Verified business badge** is shown. The detail page says business verification is incomplete. If a legally required permit is missing, the administrator must refuse publication; unverified does **not** mean permission to bypass the law.

**Scenario V06 — Earn the verified badge later**

1. Return to `/vendors`, select the business and open **Verification**.
2. Enter registration/license data and an issuing authority where applicable.
3. Attach required evidence files; ensure malware scanning succeeds.
4. Submit a verification request.
5. A separate administrator checks the official issuing source and evidence before approving.
6. Refresh the previously published listing in `/listings`.

**Expected:** The same listing gains the **Verified business** badge after backend approval/current evidence. No new listing or payment is needed merely to display the badge. Verification should not be misrepresented as an endorsement or a safety guarantee.

**Scenario V07 — Rejected business or expired license**

1. In a disposable test organization, simulate the normal administrator **rejected** decision or expired-license maintenance flow.
2. Query its previously published listings in the public directory.
3. Try submitting another listing for that organization.

**Expected:** Public visibility is suppressed and new submissions are blocked. The operator must follow remediation/renewal controls; do not set database states manually in shared/production environments.

**Scenario V08 — Add real photographs of the service**

1. Open a vendor-owned editable listing.
2. Select **Upload a real service photograph**.
3. Choose a JPG/PNG file, provide photographer/owner, an accessible description and rights confirmation.
4. Save and preview privately.

**Expected:** The local-development photo uploader sanitizes image metadata and blocks public access before the listing is published. Do not use AI illustrations as photographic evidence of real rooms or vehicles. Production storage is not yet implemented.

**Scenario V09 — Link a license reference and private document**

1. Open **Verification** in the business dashboard.
2. Enter license/registration reference, issuer and any expiry date.
3. Optionally attach a PDF, JPEG or PNG (maximum 5 MB).
4. Submit the guided action and inspect the evidence list.

**Expected:** The reference is stored and the private file is scanned by ClamAV. A pending/infected document is not treated as clean. If file upload fails after reference creation, the reference remains and the vendor must retry file upload; no silent success.

**Scenario V10 — Invite a colleague**

1. Have Tourist B sign in to Tourismo and synchronize a verified email.
2. Tourist A (business owner) opens **Team** in `/vendors`.
3. Enter B's verified email and select manager or staff.
4. Have B sign in and accept the pending invitation.

**Expected:** Email-address lookup works for existing Clerk-backed accounts. Invitation is **in-app only**, not an outbound email. Owners may delegate; staff may not self-grant owner/admin roles.

**Scenario V11 — Edit a published listing**

1. As owner/manager, open a previously published listing.
2. Propose a private revision, update accurate descriptions, room/age rules or photographs.
3. Submit the revision and open the independent admin review queue.
4. Admin approves or requests changes.

**Expected:** Visitors keep seeing the last approved version until new content is approved. Unverified businesses may revise eligible listings; revoked/expired ones are blocked. Revision approval never automatically issues a verified badge.

**Scenario V12 — Archive a listing**

1. In `/vendor/listings`, choose a published listing.
2. Archive it as the authorized owner or manager.
3. Open its former public URL.

**Expected:** The archived listing no longer appears in public search (the old link returns unavailable). Historical audit/review records are retained.

**Scenario V13 — Manage multiple organizations**

1. Register two different *test* business drafts under one owner.
2. Switch organizations in `/vendors` and `/vendor/listings`.
3. Confirm each organization contains only its own listings/documents/members.

**Expected:** Organization-level authorization isolates records. Current backend limits the number of owned business applications per account; do not try to bypass quotas through direct SQL.

## 4. Guided listing templates: six categories

These are *examples of the fields users should enter*, **not real offers**.

| Scenario | Business category | Where to enter details | Example input | What visitors can evaluate |
|---|---|---|---|---|
| L01 | Accommodation | `/vendor/listings` → accommodation | Room: Garden Family Room; adults 2; children 2; ages 4–15; nightly price estimate | Family suitability, indicative rate, house rules |
| L02 | Restaurant | Select restaurant | Cuisine: Sri Lankan; vegan options; menu with indicative LKR amounts; opening notes | Cuisine, dietary options and menu estimates |
| L03 | Local guide | Select guide | Languages: English/Sinhala; service areas; qualification notes; estimated daily fee | Spoken languages, experience area, guide claims |
| L04 | Transport | Select transport | Van: seats 8, bags 6, day-rate estimate, regions served | Capacity, luggage, service areas, price estimate |
| L05 | Tour operator | Select tour operator | Heritage circuit; places covered; duration; estimated price/person | Experience types, regional coverage and duration |
| L06 | Activity | Select activity | Village walk; minimum age; service areas; estimated price/person | Age policy, activity description and estimate |

**For all six:** Vendor details and prices are *provider-entered and indicative*; the user contacts the provider outside Tourismo. There is no live inventory, in-app inquiry channel, verified availability, tourist booking, payment, or refund in this version.

## 5. Vendor team roles

**Scenario M01 — Owner:** Create/edit organization, manage documentation, draft/submit listings, invite team members. Cannot award self a verified badge or platform admin role.

**Scenario M02 — Manager:** After invitation acceptance, edit allowed business/listing records, attach documents and submit listing changes. Cannot take over ownership or self-approve.

**Scenario M03 — Staff:** After invitation acceptance, view assigned organization information within permitted scope; owner/manager-only operations remain denied. Verify this by attempting those APIs as staff and expecting authorization failure.

**Scenario M04 — Invitation revoked:** Owner revokes a member, who then loses organizational access. Prior review/audit records are preserved.

## 6. Editor: simplify destination creation and content updates

**Scenario E01 — Create a new destination with minimal fields**

1. Sign in with an account granted editor/admin permissions.
2. Open `/admin` → **New destination**.
3. Enter a destination title and select one of Sri Lanka's districts.
4. Check the automatically filled province and generated URL slug.
5. Optionally add a short introductory summary and save.

**Expected:** Private draft created. No need to manually enter a province or invent a URL slug. Public publication is still separately controlled. Advanced slug editing remains possible for special names.

**Scenario E02 — Write a guide in a manageable sequence**

1. Choose the destination and open **Destination guide**.
2. Select English, Sinhala or Tamil.
3. Write an accurate overview, highlights and local tips; save as a private draft.
4. Expand **Sources & review information** and attach a real authoritative source URL and organization name.
5. Submit the guide for independent review.

**Expected:** Saving a draft can happen before full source research, but **publication cannot**. Already published guides retain their live version while new revisions await approval.

**Scenario E03 — Create an attraction**

1. Open `/admin` → **Add attraction**.
2. Enter attraction title; verify the automatically suggested slug.
3. Choose a category and add a useful description.
4. Supply a source URL/name; add both latitude and longitude only when they can be supported by a source.
5. Save draft, then submit.

**Expected:** Unverified coordinates are not invented. Editor cannot independently approve the attraction.

**Scenario E04 — Add your own real destination photograph**

1. Choose a destination and open **Photo & attribution**.
2. Select **My own photograph**; upload permitted JPEG/PNG.
3. Name photographer/rights holder, provide alt text and confirm rights.
4. Upload through the development media form (only administrator can attach immediately publicly visible photos under current policy).

**Expected:** Sanitized photo stored locally in development; public image gets correct descriptive attribution. Production media infrastructure is pending.

**Scenario E05 — Add AI-generated artwork responsibly**

1. Choose **AI-generated artwork** in the destination media form.
2. Upload the illustration, identify generator/model and include accessible alt text.
3. Confirm usage rights and save.

**Expected:** Discovery card and destination detail label it **AI-generated illustration**. Do not claim it depicts a real hotel interior, exact monument condition or verified entrance. This workflow uploads existing AI images; it does not generate images automatically inside Tourismo.

**Scenario E06 — Use a licensed Wikimedia Commons photo**

1. Select **Wikimedia Commons**.
2. Confirm the exact Commons file page and permissible license, author and attribution details.
3. Enter filename and alt text, choose the documented license.
4. Save using the existing admin image workflow.

**Expected:** Creator, license and source are retained. Do not paste arbitrary Google Images URLs or assume everything online is free to reuse.

**Scenario E07 — Translate a destination**

1. Select destination and change guide locale to Sinhala (`si`) or Tamil (`ta`).
2. Prepare human-reviewed local-language text.
3. Add source information and submit.

**Expected:** Language content remains draft until independent review. English fallback may be displayed where approved translations are unavailable. Machine translation alone is not evidence of accuracy.

**Scenario E08 — Content quality audit**

1. In `/admin`, choose **Content quality audit**.
2. Enable **Show only destinations with missing content**.
3. Inspect missing guides, photographs, approved attractions and languages.
4. Select a destination and address deficiencies.

**Expected:** A record in the 117-destination starter catalog is not automatically a complete guide. Quality audit is a *completeness* indicator, not proof of historical accuracy or image licensing.

## 7. Administrator: separate trust functions

**Scenario A01 — Approve destination content**

1. Sign in as an admin account with appropriate permissions.
2. Open `/admin` → **Review queue**.
3. Inspect a submitted guide/attraction and its source, accuracy and media rights.
4. Approve or request changes with actionable feedback.

**Expected:** Editor-created drafts are not auto-published. Review history is auditable.

**Scenario A02 — Verify a business and issue a badge**

1. Open `/admin/vendors`.
2. Select a submitted business *not owned or joined by the administrator*.
3. Examine registration and license references, scan-cleared documents and independent issuer evidence.
4. Record the decision/reason.

**Expected:** Only a real approval makes `business_verified` true for eligible published listings. It does not itself publish a draft listing or activate a subscription. Production MFA requirements apply to privileged actions.

**Scenario A03 — Approve content from an unverified business**

1. Open `/admin/listings`.
2. Inspect a submitted listing whose business is still `draft` or `submitted` in the verification workflow.
3. Check required category-specific legal permissions; refuse if an offer would be unlawful or misleading.
4. If the offer passes policy and content review, independently publish it.
5. Open its public page: **no verified badge**.

**Expected:** Trust label remains accurate. Administrators must not treat publication as identity validation.

**Scenario A04 — Review an already-published listing revision**

1. Open `/admin/listings` → revision queue.
2. Compare the proposed content with the live version.
3. Approve or send back with feedback.

**Expected:** Existing live content remains intact until approval; rejecting a revision does not retract the previously approved version, unless compliance rules independently suppress the organization.

**Scenario A05 — Handle license expiry**

1. In a disposable test environment, use the application's `expire` maintenance command to flag expired business evidence (requires explicit `--confirm`).
2. Recheck public listing visibility and any badges.
3. As vendor, start renewal, submit current evidence and request new verification.

**Expected:** Expired license/reference suppresses public visibility even before the next scheduled maintenance run; renewal does not grant a badge until reapproval. Don't manipulate compliance data in production to simulate this.

**Scenario A06 — Check admin conflict of interest**

1. Attempt to approve a vendor/listing owned by the current admin account.
2. Repeat with a business the admin has joined as a member.

**Expected:** Backend denies both. Platform admin status must not override this conflict-of-interest protection.

**Scenario A07 — Malware scanning of private vendor documents**

1. Start ClamAV in the existing Docker `vendor-scan` profile.
2. Upload a harmless PDF to a development business.
3. Verify scan state transitions from pending to clean only after a successful real scan.
4. Turn scanner off and try uploading another harmless file.

**Expected:** Pending file stays blocked from approved document download. Do not upload actual malware. A clean scan does not validate license authenticity.

**Scenario A08 — Handle a suspicious business (launch requirement)**

1. Receive a report of impersonation, unsafe services, false licensing or misuse of images.
2. Use documented administrative investigation and applicable existing rejection/expiry controls.
3. Preserve audit evidence and escalate for manual unpublish/suspension.

**Expected today:** Current code prevents rejected or expired-license organizations from appearing publicly; **a complete report/takedown/appeal workflow is still pending**. Do not promise automated moderation or immediate emergency suspension until implemented.

## 8. Demo-only testing

**Scenario D01 — Inspect fictional sample business listings**

1. In local `.env`, set `APP_ENVIRONMENT=development` and `ENABLE_DEMO_CATALOG=true`.
2. Rebuild the app and seed the optional fictional data pack in a disposable development database.
3. Open `/demo/listings` and filter by one of six categories.

**Expected:** 12 fictional organizations and 24 fictional listings if the data pack was seeded, clearly labeled and never available through real/public listing results. Dummy profiles cannot sign in. Demo URLs never provide real provider contacts.

**Scenario D02 — Ensure demo businesses do not receive verified badges**

1. Visit `/demo/listings`.
2. Open `[DEMO] Kandy Garden Stay` or another sample.

**Expected:** Big fictional-data disclosure; no real contacts, no booking link, no verified badge. Never manually promote the fictional SQL seed to verified.

## 9. Read-only verification scripts and database queries

### PowerShell (from project root)

```powershell
cd D:\Tourismo\Tourismo

docker compose --env-file .env -f infra/compose.yaml ps

# Avoid the Windows PowerShell 5.1 issue where Alembic INFO on stderr is treated as an exception.
docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c "SELECT version_num FROM public.alembic_version;"

powershell -ExecutionPolicy Bypass -File .\scripts\verify-pre-phase5.ps1
```

Expected migration: `0014_vendor_experience`. This visibility/UX increment does **not** create `0015` or change tables.

### DBeaver: list public services with their verification state

```sql
SELECT
    l.slug,
    l.title AS service,
    o.business_name,
    o.verification_state,
    (o.verification_state = 'approved'
       AND NOT EXISTS (
           SELECT 1 FROM public.vendor_evidence e
           WHERE e.organization_id = o.id
             AND e.expires_on IS NOT NULL
             AND e.expires_on < CURRENT_DATE
       )) AS business_verified_badge,
    l.status AS listing_review_state
FROM public.service_listings l
JOIN public.vendor_organizations o ON o.id = l.organization_id
WHERE l.status = 'published'
  AND o.verification_state NOT IN ('rejected', 'expired_license')
  AND NOT EXISTS (
      SELECT 1 FROM public.vendor_evidence e
      WHERE e.organization_id = o.id
        AND e.expires_on IS NOT NULL AND e.expires_on < CURRENT_DATE
  )
ORDER BY business_verified_badge DESC, o.business_name, l.title;
```

### DBeaver: compare approval and public listing counts

```sql
SELECT verification_state, COUNT(*)
FROM public.vendor_organizations
GROUP BY verification_state ORDER BY verification_state;

SELECT o.verification_state, l.status, COUNT(*)
FROM public.service_listings l
JOIN public.vendor_organizations o ON o.id = l.organization_id
GROUP BY o.verification_state, l.status
ORDER BY o.verification_state, l.status;

SELECT version_num FROM public.alembic_version;
```

### HTTP API sanity checks (no login required)

```powershell
Invoke-RestMethod 'http://localhost:8000/api/v1/health/ready'
Invoke-RestMethod 'http://localhost:8000/api/v1/destinations?q=Kandy'
Invoke-RestMethod 'http://localhost:8000/api/v1/listings'
Invoke-RestMethod 'http://localhost:8000/api/v1/listings?category=accommodation&adults=2&child_ages=5&child_ages=12'
```

If the API returns an empty public listing array, it may simply mean no real content has yet passed publication review.

## 10. What this release does NOT do

- No instant listing publication merely upon registration: **independent listing review remains required**.
- No self-issued verification badges: verification remains a separate admin action.
- No authorization to operate a legally regulated service without proper permits.
- No confirmed availability, booking, payment or refunds.
- No production image storage and no automatic AI-image generation within the app.
- No full SLTDA registration integration or identity check API.
- No outbound emails to unregistered invited team members.
- No mature public fraud-reporting, sanctions, risk-tiering or appeal dashboard.
- No complete real-time transit, weather or interactive map: those are later phases.

## 11. Acceptance checklist before Phase 5

- [ ] Docker app, PostGIS and ClamAV are healthy.
- [ ] `alembic_version` is `0014_vendor_experience`.
- [ ] Guest destinations, trip planner and public listing searches work.
- [ ] Google and email OTP authentication still work.
- [ ] User/profile/trip ownership checks pass with two different accounts.
- [ ] Unverified business can create and submit a complete listing for separate review.
- [ ] Publicly approved unverified listing displays **no verified badge**.
- [ ] Independently approved/currently verified business displays **verified badge**.
- [ ] Rejected/expired business listings are not public.
- [ ] Owner/admin conflict-of-interest checks remain enforced.
- [ ] Demo businesses are still explicitly fictional and not public offers.
- [ ] Destination name/district auto-fill and slug suggestions work.
- [ ] Editors cannot bypass source/approval checks; AI image label remains visible.
- [ ] Full frontend production build passes locally.
- [ ] Live PostgreSQL integration and browser tests pass.

**Only after these checks should the next map-focused increment be considered locally accepted.**
