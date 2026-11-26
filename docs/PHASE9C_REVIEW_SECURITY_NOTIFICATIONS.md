# Tourismo Phase 9C — Review ownership, trust enforcement & in-app notifications

**Baseline:** user-uploaded `Tourismo(1).zip` from 2026-11-23. This release is a **changes-only Git patch**, based on that exact archive. It does not contain credentials, existing `.env`, database dumps or complete application replacements.

## 1. What was wrong — audit findings

- `PATCH /api/v1/reviews/{id}` already contained an `author_id != user.id` rejection; **no cross-account edit was confirmed in the backend source**. Phase 9C strengthens the SQL query to include the signed-in author ID *before* acquiring a lock, retains the explicit server-side rejection, and adds regression tests for other users **including administrators**. The public review data never exposes a contributor's internal ID. Edit controls are now explicitly only shown for the current account's `/mine` results. If users still see edited data belonging to another person, investigate Clerk session switching or browser cache and send the request ID/logs, without disabling auth.
- Phase 7.1 already auto-publishes reviews after successful text/image checks. This remains intact. **Clean text auto-publishes**, suspect text goes to `pending`, rejected photo uploads return 422, unavailable photo moderation returns 503. **If `OPENAI_API_KEY` is missing or text screening fails, text stays pending**. Do not bypass checks to make all content auto-publish; configure moderation and disclose privacy implications of third-party screening.
- Existing admin review decisions included `hidden` but no obvious Remove action on published feedback. This patch adds a dedicated audited **Remove policy violation** action. It is a **soft removal**: `hidden` excludes reviews/media/replies from public views; retained evidence and audit support appeals/retention controls. Permanent erasure requires a separate privacy/retention policy and dependent-record cleanup, not ad-hoc DELETE.
- Previously there was **no persistent app-wide inbox**. Phase 9C adds one with independent account-level read states and public release announcements.

## 2. New notification events

| Event | Recipient | Notification action |
|---|---|---|
| Account session bootstrap | New / existing account, exactly once | Welcome, open account profile |
| New **published** customer review | Business owner and active managers | Open service listing |
| Admin approves a *flagged* review | Owner and active managers, once | Open service listing |
| Admin publishes provider reply | Review author | Open service listing |
| Violation takedown or reported review hidden | Review author | Notification inbox |
| Business verification decision | Business owner | Vendor profile |
| Service listing publication/review decision | Business owner | Manage listings |
| New enquiry | Business owner and active managers | Vendor inbox |
| Provider message to tourist | Tourist | Specific enquiry |
| Traveler follow-up to vendor | Owner and active managers | Vendor inbox |
| Explicit platform release announcement | Eligible signed-in users | Admin-selected internal page |

Events are saved transactionally with their business operation in PostgreSQL. A business-event failure should not leave the user seeing a successful operation that committed only half its state. User notifications use per-user `dedupe_key` uniqueness to protect against repeated welcome, publication and event retries. Pending or rejected customer reviews **do not notify providers**.

## 3. Technical design

Migration `0019_notifications_trust` **revises `0018_service_enquiries`**, adding three tables without dropping existing information:

- `user_notifications`: private account events; unique `(recipient_id, dedupe_key)`; individual `read_at`.
- `platform_announcements`: *one* release notice with explicit admin publish, unique release key and expiry. No mass fan-out to every account row.
- `announcement_reads`: individual read receipts for a release, keyed by user and announcement.

Users can read/mark **only their own** notifications. The announcement feed is shared content, but receipt status is account-specific. Only server-side event services decide a notification recipient; callers cannot send a forged recipient ID. All release URLs are restricted to local path-only routes. Provider notification recipients are owner plus active organization managers (not pending, revoked or staff), resolved from the database.

Endpoints under `/api/v1`:

| Method | Endpoint | Access |
|---|---|---|
| GET | `/notifications?limit=30&offset=0` | Signed-in owner only |
| GET | `/notifications/unread-count` | Signed-in owner only |
| POST | `/notifications/{id}/read` | Signed-in owner only; 404 for foreign/private notification |
| POST | `/notifications/read-all` | Signed-in owner only |
| POST | `/admin/announcements` | Platform admin; recent MFA in production |
| POST | `/admin/customer-reviews/{id}/remove` | Platform admin; recent MFA in production and policy reason |

The inbox includes a bell icon/count in the desktop header, a mobile-menu entry, a responsive `/notifications` page and a manual Refresh action. The bell **polls every 60 seconds** while signed in; instant device push is not claimed. Release announcement creation is available to platform admins on `/notifications`. A release key should be a unique application version, for example `tourismo-1.9.3`; publishing the same key twice returns 409. An announcement only appears to users already registered when it was published, until its expiry. An announcement is **never sent automatically on a restart**.

## 4. Non-features and future architecture

**Not included:** email or SMS delivery, Web Push, Firebase push notifications, delivery-retry workers, a connected job queue, unsubscribe/settings by category, scheduled digests, full content translation, and production-scale message delivery SLAs. These need provider configuration, consent/preferences, suppression lists, retries, bounce handling, structured observability, data-retention policy and delivery-cost assessment.

A recommended later increment is an **outbox + background worker** (persist event in the same transaction, dispatch retryably) with recipient opt-in for email/push. Do not make HTTP email calls inline during a review or enquiry transaction. Require idempotency, abuse limits, delivery logs and a provider API before claiming email/SMS support. This release intentionally remains database-local and runs without external notification credentials.

## 5. Installation on Windows PowerShell

Do **not** reapply Phase 7.1, Phase 8, Phase 9A or Phase 9B patches. Never run `docker compose down -v`, manually modify migration rows or overwrite `infra/compose.yaml` or `.env`.

**A. Inspect current deployment and back up DB** (the backup is required, even though the migration is additive):

```powershell
cd D:\Tourismo\Tourismo

git status --short

docker compose --env-file .env -f infra/compose.yaml exec -T db `
  psql -U tourismo -d tourismo -At -c "SELECT version_num FROM public.alembic_version;"
# Expected BEFORE upgrade: 0018_service_enquiries

$dbContainer = docker compose --env-file .env -f infra/compose.yaml ps -q db
if (-not $dbContainer) { throw 'No DB container found' }
$backup = "tourismo-before-phase9c-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
docker compose --env-file .env -f infra/compose.yaml exec -T db `
  pg_dump -U tourismo -d tourismo -Fc -f /tmp/tourismo-before-phase9c.dump
if ($LASTEXITCODE -ne 0) { throw 'DB backup creation failed' }
docker cp "${dbContainer}:/tmp/tourismo-before-phase9c.dump" ".\$backup"
if ($LASTEXITCODE -ne 0) { throw 'DB backup copy failed' }
Write-Host "Backup: $backup"
```

**B. Apply exactly one changes-only patch** (download the patch file to Downloads):

```powershell
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase9C_ReviewSecurity_Notifications_ChangesOnly.patch"
git -c core.whitespace=cr-at-eol apply --check $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch conflict; stop and share the diff, do not force' }
git -c core.whitespace=cr-at-eol apply $patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed' }
git -c core.whitespace=cr-at-eol diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace errors detected' }
```

**C. Build and migrate:**

```powershell
docker compose --env-file .env -f infra/compose.yaml up --build -d
if ($LASTEXITCODE -ne 0) { throw 'Docker build failed' }
docker compose --env-file .env -f infra/compose.yaml ps
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify-phase9c.ps1
```

Database **must** report `0019_notifications_trust`. The image build is responsible for invoking Alembic. On a failure inspect `docker compose --env-file .env -f infra/compose.yaml logs --tail=150 app` and stop before changing data.

**D. Manual acceptance** (two distinct Clerk users, an eligible business owner, an admin):

1. Register/sign in once; check `/notifications` has one Welcome item; sign out/in and confirm it is not duplicated.
2. User A writes an allowed text/photo review; verify immediate `published` state *when content moderation is configured and succeeds*. User B cannot edit User A's review, even by posting to the known review UUID; response must be 404.
3. User A edits one of their own five reviews; auto-screen again; user B never receives an Edit control for A's review.
4. The business owner gets a single `New customer review` notification for a new published review; pending/flagged reviews do not notify the owner.
5. Admin opens `/admin/customer-reviews`, toggles to Published, supplies a policy reason and presses Remove policy violation. The review/image disappear publicly immediately; audit/evidence remain, and the author gets a notification.
6. Admin approves a separately flagged, harmless review; it becomes public and its owner is notified.
7. Vendor posts an answer; once approved, the review author sees a notification. Test new enquiry, reply and follow-up notifications.
8. Admin publishes a unique release announcement from `/notifications`. Another signed-in user sees it, marks read, and the first user's read count is unaffected. Publishing duplicate release key gives 409.
9. Verify the original map, trip planner, destination language preview, responsive navbar, photos and five-review See more flow still work.

## 6. Testing evidence and limitations

- Backend suite in this source workspace: **266 passed, 6 skipped**, including new ownership and notification tests.
- Python source compilation passed.
- PostgreSQL Alembic **offline SQL generation** for `0018 -> 0019` passed.
- Modified TS/TSX files passed a TypeScript **syntax parse**.
- Live PostgreSQL migration, full Vite/TypeScript build, real Clerk account isolation and browser testing **not run in this workspace**. The six skipped tests require an actual PostgreSQL environment.
- Full Vite build could not be run here because the source archive has no frontend lockfile/node_modules and an offline npm install lacks the cached packages. **Your Docker build remains the definitive TypeScript and frontend gate.**

## 7. Rollback

Before deploying: keep both a Git source checkpoint and a DB backup. If source build fails **before Alembic runs**, revert this patch only using `git apply --reverse --check` and `git apply --reverse` if no newer changes are layered on top. If the migration has already run, **do not reverse the code alone and restart old app binaries**: the new tables will remain and release data may exist. Keep source/migration compatible or restore an agreed DB backup under maintenance; dropping new tables would destroy notification history.
