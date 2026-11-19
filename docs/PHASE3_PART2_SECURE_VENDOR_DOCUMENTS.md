# Tourismo Phase 3.2 — Private evidence attachments and verification renewal

## Scope and boundaries

Implemented on top of Phase 3.1 (`0008_vendor_onboarding`) without changing existing tourist, destination, trip, or approved vendor data:

- Additive migration `0009_vendor_documents`; one new `vendor_documents` table and an extra `expired_license` organization state.
- Owner/manager attachments linked to one existing license/registry reference; max 12 active files per business, 5 MiB each; PDF/PNG/JPEG only.
- Server checks extension, declared MIME, file signature, and byte size. Saved under random keys (not user filenames) in a Docker named volume (`vendor_documents`), outside Vite and FastAPI static paths.
- Uploads scanned by internal ClamAV INSTREAM when configured. If scanner is absent/unavailable, **pending_scan**, not clean. Only clean documents can be downloaded by an authorized owner/manager or an independent admin. Admin review approval is blocked whenever attached, undeleted files are not clean.
- Documents are served as attachments with no-store and nosniff headers, via protected API endpoints—not public links.
- Owner/manager can remove attachments while an application is editable. Deleted file records retain audit metadata; underlying files are removed.
- Admin reviews list attachments with scan status. A reviewer who belongs to the organization cannot download them.
- Compliance endpoint identifies expired evidence. A manual/externally scheduled maintenance command moves approved organizations with expired evidence to `expired_license`, logging an audit event. Owner can begin renewal, edit references and submit again.
- Sensitive admin review/download actions in **production** require recent (10-minute) Clerk second-factor verification as indicated by its signed `fva` claim. In development they retain the Phase 3.1 sign-in requirement.
- No public listing is created and **no vendor trial** is activated by verification.

## Apply update on Windows

From the **current** project folder (e.g. `D:\My Projects\Tourismo\tourismo_app`):

```powershell
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase3_Part2_Secure_Documents_Changes_Only.patch"
git apply --check $patch
# Only if check succeeds:
git apply $patch
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml exec app alembic current
powershell -ExecutionPolicy Bypass -File .\scripts\verify-phase32.ps1
```

Expected migration: `0009_vendor_documents`. **Do not run `down -v`**. The Docker volume `vendor_documents` stores the private uploaded file bytes. Keep backups of both PostgreSQL *and* this separate volume.

## Enable scanner for local development

The default is deliberately fail-closed: uploads stay `pending_scan`, cannot be downloaded, and cannot count as clean evidence for approval.

Set this in existing root `.env`:

```dotenv
VENDOR_CLAMAV_HOST=clamav
VENDOR_CLAMAV_PORT=3310
```

Then (the optional ClamAV image is large and requires substantial RAM):

```powershell
docker compose --env-file .env -f infra/compose.yaml --profile vendor-scan up -d clamav
docker compose --env-file .env -f infra/compose.yaml up -d --force-recreate app
# When ClamAV has initialized, re-check previously pending documents:
docker compose --env-file .env -f infra/compose.yaml exec app python -m tourismo.vendors.operations scan-pending --confirm
```

Scanner service is only on the internal Compose network; port 3310 is not published to Windows or the internet. If scanning cannot be completed, records remain pending and are not made downloadable. The official image is `clamav/clamav:stable`; ClamAV requires significant RAM to load signatures. The scanner helps detect known malware but does **not** prove that a document is authentic or free of every possible threat.

## License expiration operations

Review and schedule regular execution via your trusted scheduler; it is not started automatically in the app process:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec app python -m tourismo.vendors.operations expire --confirm
```

This only changes currently `approved` organizations **with at least one passed evidence expiry date** to `expired_license`. It records a system audit event and does not delete organizations, trips, or files. The owner can initiate re-review from `/vendors`. Renewals must be checked by a separate administrator again.

## UI and API

- `/vendors`: link a document to an existing evidence reference, upload/delete (draft or changes requested), view scan status and renewal notices.
- `/admin/vendors`: review file names/scan state, download clean documents, audit external verification source, make a decision. Admin approval still requires external HTTPS reference and independent reviewer.
- Private API: `GET/POST /api/v1/vendor/organizations/{org_id}/documents`, `GET .../{document_id}/download`, `DELETE .../{document_id}`, `GET .../compliance`, `POST .../start-renewal`.
- Admin API: `GET /api/v1/admin/vendor-verifications/{org_id}/documents`, `GET .../{document_id}/download`.

## Production-readiness limitations (must complete before external launch)

**Do not use this local-volume implementation for public production vendor uploads.** In production, upload/download are intentionally blocked with HTTP 503 unless a separate production private-storage implementation is added. Production still needs encrypted private S3-compatible object storage with short-lived signed downloads, cloud malware quarantine, file-retention/deletion policy, uploader rate limiting and request-body limits at the reverse proxy, key rotation, backup/restore drills, structured monitoring, admin account recovery, robust certificate/license validity checks, and two-person approval where appropriate.

The extension/magic-byte check is not a substitute for file parsing, content disarm/reconstruction or antivirus. Do not store passport/payment images unnecessarily. Clerk MFA must be enabled and enrolled for staff before production approval routes will accept their sessions. Reference-only verification from Phase 3.1 remains possible when no files were attached; stronger legal requirements for mandatory documents need policy decisions.

## Regression tests

Backend tests include upload/extension/signature/size rejection, fail-closed scanning, anonymous API protection, additive migration, production step-up verification, license-expiry audit, and the preexisting Tourismo suite. Live PostGIS and Clerk flows need separate end-to-end acceptance testing.
