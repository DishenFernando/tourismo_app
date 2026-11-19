# Tourismo Phase 2.4 — Editorial quality, safe revisions and completeness audit

## Purpose

Build on migration `0005_rich_destination_review`, without replacing the existing app, authentication, user profiles, trips, destination records, or Docker configuration. This increment concentrates on editorial integrity rather than adding more unreviewed place names.

## Changes

1. **Published guide protection**. Editing a `published` or existing `sample` destination guide creates an unpublished `destination_guide_revisions` record. The public guide remains accessible, with its original approved content and `content_status`, until explicit administrator approval. Drafts and submitted updates never appear through guest destination APIs.
2. **Reviewable updates**. An editor submits a sourced revision, an admin approves it or returns it to draft with a reason. An approved revision records approver and timestamp; new versions have sequential revision numbers. Re-saving a submitted revision is rejected (409). New guides that have not been published use their existing Phase 2.3 workflow.
3. **Content-quality audit**. New editor/admin-only `GET /api/v1/admin/content-audit` identifies incomplete destination records across the current catalog: unpublished/sample destination, no published English guide, no credited photograph, no published POIs, and missing approved Sinhala/Tamil guides. Counts represent **workflow completeness, not validation of factual accuracy or media rights**.
4. **Admin dashboard**. New **Content quality audit** tab with catalog/published/attention counts, destination-level missing items, incomplete-only filter, and a shortcut to edit that destination.
5. **Read-only local verification script**: `scripts/verify-phase24.ps1` checks Docker, API readiness, guest discovery, current Alembic revision, catalog counts and anonymous admin rejection.
6. **Regression coverage**: tests for keeping published content live during edits, approving updates, rejecting revisions, audit semantics and migration declarations.

## Migration

`0006_editorial_quality` creates only `destination_guide_revisions` and indexes. No data migrations, destructive updates or seed changes. Normal application startup runs `alembic upgrade head`. Existing photos, 117 initial catalog destinations, roles, accounts and trips remain intact. Never run `docker compose down -v`.

## Install — changes-only Git patch

From VS Code PowerShell:

```powershell
cd D:\Tourismo\Tourismo
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase2_Part4_Editorial_Quality_Changes_Only.patch"
git apply --check $patch
# Apply only when check succeeds:
git apply $patch
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
powershell -ExecutionPolicy Bypass -File .\scripts\verify-phase24.ps1
```

Do not overwrite your `.env`. If `git apply --check` fails, merge the conflicting files rather than forcing the patch.

## Manual acceptance tests

1. Sign in as the database-granted **editor**. Open `/admin`, **Content quality audit**. Verify the list represents unfinished content rather than falsely labeling all catalog rows fully verified.
2. Select a currently **published** destination. Record its public guide text in a separate browser tab.
3. Change the source-backed guide in Content Studio and click **Save guide draft**. Refresh the public page; it must still display the *old* approved guide.
4. Click **Submit for review**. Confirm the guide revision appears in the administrator's review queue and is invisible to guests.
5. As admin, inspect the revision. Request changes to verify the public guide still stays live; resubmit after any corrections, then approve.
6. Refresh the public page. Only now should the approved revision appear. The `destination_guide_revisions` table retains the approved revision and the `audit_events` table retains the decision trail.
7. Recheck the user profile, Google/email login, guest draft survival, saved trips and ownership isolation as Phase 1 regressions.

Database checks:

```sql
SELECT version_num FROM alembic_version;
SELECT status, count(*) FROM destination_guide_revisions GROUP BY status ORDER BY status;
SELECT content_status, count(*) FROM destination_guides GROUP BY content_status ORDER BY content_status;
SELECT content_status, count(*) FROM destinations GROUP BY content_status ORDER BY content_status;
SELECT action, reason, occurred_at FROM audit_events ORDER BY occurred_at DESC LIMIT 20;
```

## Limitations and next actions

- A source hyperlink is a reference, **not** proof of editorial or legal verification. An admin must check accuracy and media rights. No new photo assets are added in this increment.
- Review history begins with revisions created after migration `0006`. Earlier initial published/sample guide content is not backfilled as an immutable historical snapshot.
- The complete content structure required by the blueprint (best seasons, transport, accessibility, emergency institutions, price-band provenance, regional specialties, detailed family/elder suitability) is **not yet implemented**. Add structured, versioned fields only when sufficiently verified source material exists.
- Sinhala/Tamil authoring and review workflow exists, but the catalog is not populated with reviewed translations. This is intentionally flagged in the audit.
- The admin system is editorial-only. Full platform user management, vendor organization approval, moderation, finance and step-up MFA are not implemented.
- Background image URL health checks, content source freshness expiry, structured metadata, browser E2E, load tests, backups, and production deployments remain pending.
- The updated Python tests are offline tests; run the Docker and authenticated browser checks above to establish local runtime correctness.
