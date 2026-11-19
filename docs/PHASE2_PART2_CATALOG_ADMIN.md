# Tourismo Phase 2.2 — Expanded destinations, credited photography, admin CMS

## What this release includes

- **117** destination, town, park and landmark seed entries spanning all **nine provinces**. The old five entries are retained; `ON CONFLICT DO NOTHING` never overwrites an existing title, guide, or other edited record.
- **18** photo records from **Wikimedia Commons**, with credited creators, file detail page, CC license and license URL displayed with images. These are remotely hosted images, not downloadable assets embedded in this archive; they require internet access. If remote loading fails, the illustration remains visible. Images are limited to individually identifiable locations; we deliberately do not attach unrelated stock photos to the rest of the catalog.
- New `destination_photos` database table and extended public destination API.
- Province filtering, image cards and destination hero photography with attribution.
- New `/admin` editorial dashboard; adding destination drafts, writing guides, creating attraction drafts, linking properly credited photographs, approving destinations, and approving sourced attractions.
- Clerk-verified user accounts remain separate from **platform `admin` and `editor` roles** in PostgreSQL. New sign-ups are not admins by default.
- Audit records for content changes and role-management commands.

## Apply safely

Use the accompanying Git patch against the **Phase 2.1** version of Tourismo. Do **not** overwrite your `.env`, `infra/compose.yaml`, or database volume. Before applying, commit/backup your local work and use `git apply --check`.

```powershell
cd D:\Tourismo\Tourismo
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase2_Part2_Catalog_Admin_Changes_Only.patch"
git apply --check $patch
git apply $patch
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
```

Alembic automatically adds revision `0004_catalog_admin_media` on app startup. **Never run `down -v`**.

## Create your first admin securely

1. Sign in to Tourismo normally through **Clerk Google or email OTP**. This inserts your verified Clerk subject in PostgreSQL `users`.
2. In DBeaver, confirm the target user, using a verified Clerk account ID, not only the email address:

```sql
SELECT id, auth_subject, email, display_name FROM public.users ORDER BY created_at DESC;
SELECT key, description FROM public.platform_roles ORDER BY key;
```

3. With shell access to your own trusted Docker host, run this command, replacing the placeholder with **the exact `auth_subject`**:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec app `
  python -m tourismo.admin.cli grant --subject user_REPLACE_WITH_REAL_CLERK_SUBJECT --role admin --confirm
```

4. Refresh the browser and account permissions (or sign out and sign in again). The account menu will then contain **Content dashboard**. Visit `http://localhost:8000/admin`.
5. To add an editor use `--role editor`. To revoke access:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec app `
  python -m tourismo.admin.cli revoke --subject user_REPLACE_WITH_REAL_CLERK_SUBJECT --role admin --confirm
```

**No default admin password, email whitelist, or public administrator registration endpoint exists.** Only a trusted operator with shell/DB access can assign admin. Protect your Docker host, database credentials and Clerk backend key. Before production, add MFA for privileged users, dual-approval and CSRF/abuse controls appropriate to your deployment.

## API smoke tests

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
Invoke-RestMethod http://localhost:8000/api/v1/destinations?q=Sigiriya
Invoke-RestMethod http://localhost:8000/api/v1/destinations/sigiriya
```

The public endpoints must allow guests. The admin endpoints must return HTTP 401 when no Clerk session is present, and HTTP 403 for an authenticated tourist without roles.

## DBeaver verification

```sql
SELECT version_num FROM alembic_version;
SELECT count(*) FROM destinations;
SELECT province, count(*) FROM destinations GROUP BY province ORDER BY province;
SELECT count(*) FROM destination_photos;
SELECT key FROM platform_roles ORDER BY key;
SELECT d.slug, p.photographer, p.license_name, p.file_page_url
  FROM destination_photos p JOIN destinations d ON d.id=p.destination_id
  ORDER BY d.slug;
```

Expected version: `0004_catalog_admin_media`. On an unmodified foundation DB, expect 117 destinations (including the original five) and 18 credited photograph records. Existing custom records may raise the destination count.

## Important editorial and technical limitations

- This is **not a complete catalog of every Sri Lankan village, attraction, or tourism provider**. These 117 are a broad starter directory requiring editorial review for precise administrative boundaries, access details and descriptions.
- Unverified sample pages are labeled. Draft guides and attractions do not appear publicly. New translations need native-speaker review.
- Wikimedia Commons attribution and CC licenses must remain visible. Several CC BY-SA licenses impose obligations on adapted images. The app links to originals rather than embedding the image binaries. No author approval or automated license validation is implied.
- Adding a Commons filename in the dashboard is a trusted administrator action: editors must independently check the exact photograph, license, creator and permitted reuse. No automatic infringement detection is present.
- Photograph URLs resolve remotely; if Wikimedia blocks hotlinking or the browser has no network access, the decorative placeholder remains. For production, import licensed originals into a managed media library with correct license metadata and permitted transformations.
- This release is a first CMS, **not** a finished production editorial workflow: no version diff, cross-editor review, asset upload/storage, photo cropping or per-field moderation yet.
- No new tourist booking/payment functionality is introduced.
