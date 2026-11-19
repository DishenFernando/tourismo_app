# Tourismo — Implementation audit against Master Blueprint v1.1

**Review basis:** source in the Phase 2.3 project, the added Phase 2.4 changes, and `docs/MASTER_BLUEPRINT_v1.1.md`. A feature is called implemented if code/schema exists; this does **not** imply user acceptance or production readiness.

| Blueprint workstream | Observed implementation | Missing / outstanding verification | Priority |
|---|---|---|---|
| Phase 0 — product discovery | Blueprint, brand kit, architecture and initial roadmap | User interviews, competitive evidence, legal/data licensing approvals, supplier pipeline, live usability checks | Before public beta |
| Phase 1 — runtime | Docker with React/Vite + FastAPI and PostGIS; Alembic migrations, health endpoints, GitHub Actions configuration | Verify latest workflow run, full container restart and live Postgres tests; production secrets, security review and recoverable backups | P0 |
| Phase 1 — auth and profiles | Clerk Google/email integration, post-login user provisioning, header account menu and editable profile; protected APIs | Run actual Google/email signup and provisioning tests, identity-linking tests, deactivated-user case, CSRF/origin checks, cross-account trip isolation | P0 |
| Phase 1 — guest planning | Guest draft, group/children fields, budget preview and cloud save | Browser regression for guest draft through signup and return, ownership, mobile layouts and export coverage | P0 |
| Phase 2 — catalog | 117 initial destination records across nine provinces, sample descriptions | Most are directory records, not fully researched guides. No invented listing/review/availability data should be added to fill gaps | P0 content |
| Phase 2 — photography | 18 credited remote Commons photo records from earlier phase, gallery UI | Independent file page/licensing audit, more matching images, image availability and proper provenance beyond declared fields | P1 |
| Phase 2 — POI and geography | Sourced sample POIs, four UNESCO reference coordinates, map links | Full locality hierarchy, verified POI coords/entrances, essential service institutions, mapping, accessibility | P1 |
| Phase 2 — translations | `en/si/ta` schemas, admin editor and public English fallback | Almost all native-language guides remain unreviewed/unwritten; verified Sinhala/Tamil editorial content | P1 |
| Phase 2 — editorial | Admin/editor roles, drafts, review queue, approval, audit events; Phase 2.4 non-disruptive guide revisions and readiness dashboard | Independent content reviewers, photos rights verification, richer field-level source freshness/expiry, complete admin review history | P1 |
| Phase 3 — vendor identity | Not implemented | Vendor organizations, verification, proof files, scoped staff roles, document privacy and approval | Next major phase after Phase 2 exit |
| Phase 4 — listings | Not implemented | Hotels/stays, restaurants, guides, transport services, category inventory, media and sourcing | P1 |
| Phase 5 — search/map | Basic destination query and province selection only | Real vendor filtering, child-age-aware accommodation search, spatial expansion, 2D provider map | P1 |
| Phase 6 — trip/budget | Minimal guest builder already in Phase 1 | Editable cloud trips, exports/favorites, collaboration, real verified cost estimates | P1 |
| Phases 7–14 | Not implemented | Transport/safety; reviews/moderation; subscriptions; merchant payments; grounded assistant; beta; observability; 3D | Per roadmap |
| Deferred tourist booking | Deliberately not implemented | Tourist checkouts, reservation holds and refunds are separate PH2, not vendor subscriptions | Later |

## Critical gaps detected in this source review

1. **A published guide could disappear on editing:** previous `save_guide()` set the existing live guide to `draft`. Fixed in Phase 2.4 by isolating new revisions until administrator approval.
2. **Catalog size was conflated with content quality:** 117 place names does not equal 117 verified travel guides. The Phase 2.4 audit reports missing published guides, photos, POIs and reviewed localizations.
3. **Permission controls are present but need acceptance evidence:** backend admin/editor role checks are server-side, yet production MFA, platform super-admin scope and two-person sensitive actions remain outside current implementation.
4. **Live integration gaps remain:** offline unit tests skip PostgreSQL integration; no claim of production build/browser tests until observed on the running deployment.
5. **Content claims and rights must be managed:** source URLs and Commons attribution fields do not independently verify a source's accuracy or its current redistribution license.
6. **Phase 2 exit criteria from the blueprint:** rather than endless shallow records, fully validate **3–5 high-quality destinations** and their sourcing, public guide, POIs, and localization readiness before launching vendor onboarding.

## Recommended sequence

1. Apply Phase 2.4 safely, run migration and full browser workflow including published guide revision.
2. Deepen a **five-destination pilot** (Kandy, Galle, Anuradhapura, Sigiriya and Nuwara Eliya) with reviewed attraction details, photos and practical sourced content. Prioritize source quality over arbitrary completeness.
3. Confirm images/rights, improve translations and run usability, security, accessibility and live DB tests; record Phase 2 acceptance evidence.
4. Move to Phase 3 vendor organization onboarding with private document storage, admin approval, verified staff scopes and role permissions.
