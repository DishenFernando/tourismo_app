# Tourismo Phase 10A — Operational Readiness & Release Gates

**Purpose:** Add practical, read-only production configuration auditing, reproducible backups, optional container readiness monitoring, and a smoke verifier. This is **not** a claim that Tourismo is production-certified. This increment does **not** enable email, SMS, browser push, booking, payments, third-party APIs, or silent automated announcements.

## Source and deployment assumptions

- Built against the owner's `Tourismo(1).zip` source with the Phase 9C notifications/trust patch applied as the next change. **Requires schema `0019_notifications_trust`.**
- Existing stack: Python 3.12/FastAPI, PostgreSQL 16/PostGIS, Docker Compose, React/Vite, Clerk.
- Phase 10A changes **no application runtime source, `.env`, existing Compose file, existing migrations or database rows**. It only adds scripts, documentation, and an optional separate Compose overlay.
- Existing `/api/v1/health/live` and `/api/v1/health/ready` endpoints are reused. The application retains its existing guest/auth rules.

## Files

- `scripts/phase10_release/production_audit.py` — offline environment/configuration audit with no secret value output.
- `scripts/phase10_release/test_production_audit.py` — regression tests.
- `scripts/phase10_release/backup-tourismo.ps1` — PostgreSQL custom-format backup and private-document snapshot outside the Git checkout.
- `scripts/phase10_release/verify-phase10.ps1` — live/ready, migration, private inbox smoke checks (read-only).
- `infra/compose.phase10-health.yaml` — **optional** application healthcheck overlay; existing Compose remains untouched.

## Installation (Windows PowerShell 5.1)

1. Install/verify Phase 9C first, including `0019_notifications_trust` and a successful Docker build. Phase 10A can be applied as a new-file-only patch; do not apply old phase patches again.
2. Back up and inspect before applying: `git status --short`, `git apply --check <Phase10A patch>`.
3. Apply with `git apply <Phase10A patch>`. Do not use force or reset.
4. Run offline regression tests:

   ```powershell
   py -3 .\scripts\phase10_release\test_production_audit.py
   py -3 .\scripts\phase10_release\production_audit.py --root . --mode local
   ```

5. With existing app/db running:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase10_release\verify-phase10.ps1
   ```

6. Optional container healthcheck (no app code change):

   ```powershell
   docker compose --env-file .env -f infra/compose.yaml -f infra/compose.phase10-health.yaml config --quiet
   docker compose --env-file .env -f infra/compose.yaml -f infra/compose.phase10-health.yaml up --build -d
   docker compose --env-file .env -f infra/compose.yaml -f infra/compose.phase10-health.yaml ps
   ```

   Use `--quiet`; full Compose config output may include secrets.

## Creating a recovery snapshot

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\phase10_release\backup-tourismo.ps1 `
  -ProjectRoot . -BackupRoot "$env:USERPROFILE\TourismoBackups"
```

- Uses `pg_dump -Fc` and validates the archive listing with `pg_restore -l` **without restoring or mutating the database**.
- Copies the running app's `/app/private_vendor_documents` data to a timestamped local directory.
- Generates SHA-256 manifest for the DB dump. It does not include `.env`, TLS/Clerk credentials or external media. Private uploads are confidential: protect access, encrypt, then move offsite. Do not commit backups.
- `pg_restore -l` proves file readability, **not recoverability**. At least once per release cycle, restore the DB and private files to a separate test stack and verify records/media/authorization there. Never run a destructive restore on live Tourismo.
- Multi-container consistency is not automatic: if document writes are in flight, coordinate a controlled snapshot/backup window. Establish retention, rotation and restore RTO/RPO operationally.

## Production blocker audit

Run `py -3 .\scripts\phase10_release\production_audit.py --root . --mode production` only against a **locally secured** set of deployment settings. It checks (without printing values):

- Environment mode, database URL not using local/dev defaults, Clerk HTTPS configuration, allowed authentication/CORS HTTPS origins, disabled demo and unconfigured phone OTP.
- Presence of ClamAV and HTTPS map tile URL.
- Development Compose password and direct application port exposure.
- Whether `.env` is tracked by Git.
- Phase 9C migration source exists, with correct revision.

**The development Compose is expected to FAIL this production audit.** Do not “fix” that by blindly editing a working development stack. Build a separate real production deployment, set secrets in a managed secret store and review TLS/edge network policies, DB credentials, verified provider configuration and license obligations. Static auditing does not prove secrets are valid.

### Manual launch blockers that automation cannot certify

| Area | Required evidence |
|---|---|
| Privileged access | MFA/role regression across guest, tourist, vendor staff, owner, editor, admin; real Clerk sessions |
| Data protection | Privacy/legal signoff, retention/deletion policy, user data export, audit/event retention |
| Trust | Text/photo moderation, vulnerability review, review appeals, vendor evidence scanning, legal complaint response |
| Operations | Encrypted offsite DB AND private documents, isolated restore drill, monitoring, alert ownership, paging on-call |
| Scalability | Shared/distributed rate limiting, load tests, managed PostgreSQL capacity, idempotent webhook/message handling |
| Public delivery | TLS/HTTPS, DNS, CSP and security headers, static assets, compliant tile provider, CDN/image licenses |
| SEO & languages | Correct canonical metadata/prerender strategy, native-reviewed Sinhala/Tamil content before claiming localization |

## Notification release protocol (from Phase 9C)

Phase 9C uses **persistent in-app notifications** only. Publish a release announcement **manually** through an authenticated admin only after deployment, schema and smoke tests pass. Use a unique release key, concise changelog, targeted audience and sensible expiration. Do not fire announcements on container startup or on failed deployment. Outbound email/SMS/mobile push requires a separate consent-aware, queued delivery design and a configured provider. This phase does not silently add an external provider.

## Rollback and safety

All Phase 10A changes are new files only and have no database migration. If not applied, nothing changes. To revert a successfully applied Phase 10A patch use `git apply -R <patch>` **only after** checking `git apply -R --check <patch>` and verifying no subsequent edits to those files. Optional healthcheck overlay is removed from the command line to disable it. Do **not** call `docker compose down -v`, delete Docker volumes, manually alter `alembic_version` or restore over production data.
