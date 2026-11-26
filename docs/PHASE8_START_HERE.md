# TOURISMO Phase 8 — Installation quick start

1. **Prerequisite:** Phase 7.1 installed and verified in your own Docker/Clerk environment; current database revision `0017_review_media`.
2. **Backup your database** using `docs/PHASE8_TOURIST_VENDOR_ENQUIRIES.md`.
3. **Apply only one update format**: `Tourismo_Phase8_Enquiries_Changes_Only.patch` (recommended) OR update-only ZIP. Use `git apply --check` first.
4. Rebuild: `docker compose --env-file .env -f infra/compose.yaml up --build -d`.
5. Check schema and guest restrictions: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase8.ps1`.
6. Browser test: published real listing -> tourist enquiry -> vendor owner reply -> traveler follow-up -> report -> admin review/decision. Validate saved trips/maps/reviews still operate.

### Pages

- Tourist `/enquiries`
- Provider `/vendor/enquiries`
- Admin `/admin/enquiry-reports`
- Real service listing `/listings/{slug}` includes the enquiry form

**No booking, payment, attachments, or outbound email in this release.** Source tests do not replace real Docker/PostgreSQL/Clerk and browser acceptance. Do not drop data volumes.
