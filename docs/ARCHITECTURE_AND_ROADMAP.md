# Tourismo — technology, modular architecture, database and full delivery roadmap

**Requirements baseline:** Tourismo Master Blueprint v1.1. P0/P1/P2 in the blueprint are *feature priorities*; engineering phases are numbered 0–14. These are not interchangeable.

## Architectural dependencies
```
React public UX -> FastAPI public routes -> Geography/approved editorial content -> PostgreSQL/PostGIS
React guest planner -> Stateless preview API -> Validated itemized budget calculation
React protected actions -> Clerk Google/email verification -> FastAPI JWT/JWKS verification
Verified identity -> Local users auth_subject -> Ownership-scoped cloud trip persistence
Provider organization -> document verification -> approved listing -> public discovery
Published listing -> vendor contact/inquiries and eligible moderated reviews
Approved organization/listing -> one trial -> subscriptions -> invoices -> verified payments
Only curated/approved/source-backed data -> search -> deterministic AI assistant
Platform staff permissions -> verification, moderation and finance controls + immutable audits
```

All endpoints derive permissions from server-managed roles/memberships; never from client-sent role claims. Privileged roles, document handling and subscription/payment endpoints are intentionally not implemented in Phase 1.

## Stack decisions
| Layer | Choice | Notes |
|---|---|---|
| Web | React 19, TypeScript, Vite, React Router, Tailwind | SEO prerender/SSR is required before serious organic acquisition |
| Identity | Clerk Google and verified email OTP | Developer keys must be configured; verify backend issuer, signature, time, azp; privilege MFA before commercial launch |
| API | Python 3.12, FastAPI/Pydantic | Modular monolith, `/api/v1`, OpenAPI |
| Data | PostgreSQL 16/PostGIS, SQLAlchemy 2, Alembic | Foreign keys, JSONB only for flexible elements; later normalize schedules, listings, review dimensions |
| Search | PostgreSQL full text / pg_trgm / geo GiST | Avoid external search cluster until needed |
| Maps | MapLibre + licensed tiles later | Never present fictitious live maps/locations |
| Testing | Pytest, Vitest, future Playwright and PostgreSQL integration suite | Real identity login needs provider test tenant |
| Operations | Compose; GitHub Actions; Render/Neon demo | Render Free is not reliable production infrastructure |
| Media | Approved managed media provider later | Private KYC and bank proof need separate private storage and malware scanning |

## Initial database — migrated today
```
users (auth_subject UNIQUE, status, locale)
  |--< user_role_assignments >-- platform_roles (future privileged scopes)
  |--< trips (owner_id, destination_slug, dates, travelers, private budget, stops)
  |--< audit_events (future actor audit event foundation)
content_sources (license_status, verified_at)
  |--< destinations (slug, district, province, geography Point, status)
         |--< destination_translations (unique destination_id,locale)
```

- Guest requests never create `users` records. A provider-verified subject creates one linked row on the first authorized request.
- `trips.owner_id` is enforced on every cloud-trips read, and missing records for another owner return 404.
- PostGIS GiST index is included for destination geography groundwork; no unverified routing claims.
- No real vendor data is seeded. Place-name-only examples are `content_status=sample`, shown with a label.
- Phase 3 onward expands separate organization, membership, evidence, and eligibility states.

## Later domain schema
The blueprint defines tables across these groups, to be migrated as features arrive, not created as unused empty tables: 
- Geography: `geo_regions`, `poi`, `content_sources`, `destination_guides`, `events_festivals`, emergency services.
- Providers: `vendor_organizations`, `vendor_branches`, `vendor_memberships`, `vendor_documents`, `vendor_verification_checks`.
- Listings: `listings`, `accommodation_properties`, `unit_types`, `rates`, restaurants/menus, vehicles/rates, guides/activity packages, media, hours.
- Planning: `trip_days`, `trip_stops`, `trip_budget_items`, `trip_expenses`, share tokens, collaborators, revisions.
- Trust: `inquiries`, `messages`, `reviews`, `review_evidence`, `content_reports`, `moderation_decisions`, `appeals`.
- Money: `subscription_plans`, `plan_entitlements`, `vendor_subscriptions`, `subscription_invoices`, `payment_attempts`, `gateway_events`, `bank_payment_proofs`, `payment_reviews`.
- Operations: `notification_outbox`, support tickets, audit events, feature flags, grounded AI sessions.

## Complete roadmap — blueprint section 42 preserved
| Engineering phase | Functional deliverable | Exit gate |
|---|---|---|
| 0 Discovery | Interviews, competitor study, source license/legal register, wireframes | Evidence of customer/vendor fit and data permission |
| 1 Foundation | Branding, public SPA, FastAPI, PostGIS, migrations, OIDC gate, cloud trip baseline | Anonymous search, guest draft, real auth, owner-scoped storage test |
| 2 Geography/editorial | 3–5 reviewed destination guides, multilingual CMS & POIs | Source-reviewed realistic content |
| 3 Vendor onboarding | Organization enrollment, evidence/license review, staff scopes | Public listing only after approval |
| 4 Provider inventory | Accommodation units/rates, menus, vehicles, guides, authorized images | Complete usable vendor profiles |
| 5 Search/maps | Verified filters, family room combinations, radius 5/10/20/40 km, licensed 2D map | Family/Nuwara Eliya searches correct |
| 6 Planning/budgets | Itinerary days/stops, sync, expenses, category ranges, shares and export | Full group plan with truthful estimates |
| 7 Transport/safety | Official train/bus links, sources, weather and emergency points | No unsupported live status |
| 8 Trust/reviews | Genuine eligibility, responses, scam reports, appeals | Fair moderation and audit test |
| 9 Subscriptions | One organization trial, plans, invoices, private bank-slip review | No slip-alone activation or trial farming |
| 10 Gateway | Approved hosted checkout, signature-verified webhook, idempotency | One paid activation under duplicate callbacks |
| 11 Assistant | Deterministic grounded assistant, structured sources, safe fallback | Source validation and non-hallucination suite |
| 12 Beta | Security/accessibility/load test, real pilot content and vendor testing | Signed public beta launch criteria |
| 13 Operations | Backup/restore, monitoring, cache, analytics, ranking improvements | Verified measurable production performance |
| 14 Advanced web | 3D, richer routing, paid licensed feeds, optional RAG | Provider agreements and spend controls |
| PH2 Bookings | Customer bookings/holds/payments/refunds only after feasibility/legal project | Separate launch gate |
| MOB Native | Expo/React Native API reuse, device security, optional licensed offline | Android/iOS acceptance |

## Phase 1 implementation verification plan
- [x] Initial app with official brand assets and responsive guest public pages.
- [x] Public REST search over actual PostgreSQL schema (requires local stack running).
- [x] Versioned PostGIS database migration, small labeled sample place seeds.
- [x] Guest planner draft, ages, editable day stops, manual budget, API preview.
- [x] Clerk-compatible sign in UI and backend JWT validation code.
- [x] Own-trips server-side guarded cloud save/read API.
- [x] Backend + frontend unit test files and CI jobs.
- [ ] Run full stack in Docker on a machine with Docker installed.
- [ ] Configure actual Clerk application and verify Google/email OTP end-to-end.
- [ ] Verify real user A cannot access user B's private trip with two Clerk sessions.
- [ ] Validate 320/768/1440px UX on browser/device and run automated Playwright checks.
- [ ] Full deployment, licensed maps, live weather, vendor inventory: future phases.
