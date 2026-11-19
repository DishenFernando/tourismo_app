# Tourismo — Phase 0 discovery, deliverables, and release gates

**Status:** Architectural and planning artifacts prepared; customer research and approvals are NOT complete.
**Source of truth:** `MASTER_BLUEPRINT_v1.1.md`, particularly Parts A, B, H and I.

## Scope and business outcomes
- Understand the needs of Sri Lankan families, groups, solo visitors, international visitors, older travelers and accessibility-dependent travelers.
- Validate why combining destinations, credible vendors, transport, trip budgeting and safety information is valuable enough to use.
- Validate a sustainable business model that charges **vendors for subscriptions**, not tourists for Phase 1 bookings.
- Start with real/approved local supply before marketing broad coverage.

## Required Phase 0 work products
| Work item | Planned artifact | Acceptance evidence | Status |
|---|---|---|---|
| Interviews | 20–30 tourist interviews and 15–20 vendor interviews | Recorded anonymized findings and themes | NOT DONE |
| Competitor analysis | Feature/task matrix: Booking.com, Agoda, Tripadvisor, Google Maps, local options | Actual comparison of the same trip-planning tasks | NOT DONE |
| Pilot destinations | 3–5 regions, initial candidate Anuradhapura/Nuwara Eliya + contrasting area | Vendor density, source coverage, research-based choice | PROPOSED |
| User journeys | Family 2+3 children ages 4,9,13 / Nuwara Eliya group 6 / guide / vendor / AI | Scenarios documented in blueprint sections 6–10 | DOCUMENTED |
| Permission matrix | Guest/tourist/applicant/vendor/finance/admin/superadmin | Blueprint section 12.2 and API contract | DOCUMENTED |
| Legal/data rights | SLTDA categories, PDPA & international processors, OSM/weather/rail source licensing, payment merchant | Reviewed data-source ledger + legal signoff | NOT DONE |
| Vendor monetization | One 30-day trial after first listing approval, plan configuration, post-trial entitlement | Research and owner approval before launching billing | PROPOSED |
| UX | Responsive branded public home, first-visit search and just-in-time sign-in concept | Functional starter screens plus human testing | STARTED |
| Security | Abuse, BOLA, upload, license, payment replay, admin MFA threat register | Reviewed negative tests and risk signoff | STARTED |
| Technical feasibility | React/FastAPI/PostGIS/OIDC, Render/Neon constraints | Local integration test and a demo deployment | STARTED |
| Public sources | Provenance and permissible commercial use | Verified links, usage terms, last-checked policy | NOT DONE |
| Branding | Tourismo official SVG/PNG pack | Assets copied into UI; trademark/domain clearance | ASSETS INTEGRATED, CLEARANCE PENDING |

## Explicit owner decisions (proposed defaults, not silent decisions)
1. Pilot areas: focus on Anuradhapura, Nuwara Eliya and one contrasting region after research.
2. Currency: LKR; all stored monetary amounts in minor units.
3. Managed identity: Clerk Google + verified email codes for foundation; conditional on permitted MFA levels for privileged finance/admin before production.
4. Phone SMS OTP: disabled until a real approved paid SMS provider is onboarded.
5. Trial begins on *first approved listing*, not signup; 30 days exactly once per verified organization.
6. Basic listing visibility post-expiry: proposed to remain accessible while premium lead entitlements lapse; research/approval required.
7. Tourist bookings, checkout, paid reservations: Phase PH2 only.
8. Trip guest draft: browser session only; explicit confirmation before cloud import.
9. Map tiles and weather services: no unlicensed default production feed.
10. Source claims: no public verified designation without review evidence.

## Phase 0 exit / acceptance
- [ ] At least one tourist audience validates meaningful value through research.
- [ ] Vendor interviews demonstrate willingness to supply credible inventory, with realistic costs.
- [ ] Pilot region choice supported by real data coverage, not simply scenic appeal.
- [ ] All external source licensing and privacy dependencies documented.
- [ ] Critical user journeys and data ownership policies signed off.
- [ ] Trademark/domain and company/legal obligations reviewed before launch.
- [ ] An approved scope distinguishes P0, P1, P2, PH2 and mobile.

Phase 0 is **not complete** until these external activities are evidenced. The software foundation can proceed in parallel.
