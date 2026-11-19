# Tourismo Phase 1 — Google/email users and tourist profiles

## Why Clerk accounts previously did not appear in `public.users`

Clerk owns authentication identities. Earlier Tourismo frontend code never called the protected API immediately after sign-in. `require_user` only created a record on subsequent calls such as `/me` or `/trips`, which users did not necessarily initiate. The result was valid Clerk accounts with no corresponding Tourismo row.

## Changed behavior

1. Every completed Clerk sign-in (Google **or** email OTP) triggers the authenticated `POST /api/v1/auth/session/bootstrap` from `ConnectedAuth`.
2. The FastAPI endpoint validates the signed, short-lived session using Clerk JWKS, issuer, origin and subject. Its shared `require_user` dependency creates the `users` record with a unique `auth_subject` if none exists. Repeated calls cannot create duplicates.
3. The endpoint can securely retrieve the *verified primary email* and Clerk name through Clerk's **server-only** Backend API when `CLERK_SECRET_KEY` is present. It never trusts a browser-submitted email or role. It doesn't overwrite a name the tourist already customized.
4. The top-right header displays Clerk's real avatar and the saved display name. It has My profile, Sign-in & security, and Log out actions; mobile has the same profile navigation.
5. Signed-in users can update private Tourismo data at `/account`: display name, preferred language, home region, and optional bio. None are public reviews, listings, or permission grants.
6. New accounts see a dismissible completion reminder. Profile completion is optional: guests can still explore and signed-in users may still save trips without completing extra profile fields.

## DBeaver location

Database `tourismo`, schema `public`, table `users`:

```sql
SELECT id, auth_subject, display_name, email, locale, home_region,
       profile_completed_at, status, created_at
FROM public.users
ORDER BY created_at DESC;
```

`auth_subject` maps the Tourismo PostgreSQL UUID identity to a Clerk `user_...` subject. Clerk remains the system of record for Google/email credentials, email verification, active sessions, and profile images. **Never** store Clerk passwords, tokens or secret keys in `users`.

## Local setup / upgrade

- Keep the existing root `.env` file. Never extract a package over your actual `.env` or commit it.
- To synchronize verified email into PostgreSQL, obtain the **Secret key** from your own Clerk Dashboard → API keys and add `CLERK_SECRET_KEY=sk_test_...` to the root `.env`. This value is **server-only**, must never start with `VITE_`, and must never be committed, pasted or exposed in screenshots. If it is absent or Clerk is unavailable, login/profile creation still work, but verified email won't be copied to `users.email`; the frontend can still display the email supplied by Clerk's authenticated `useUser` hook.
- `DATABASE_URL` inside Docker remains `postgresql+psycopg://tourismo:tourismo_dev@db:5432/tourismo` for development. DBeaver uses localhost:5432.
- Run from repo root:

```powershell
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
docker compose --env-file .env -f infra/compose.yaml logs --tail=50 app
```

- Startup runs `alembic upgrade head`, applying **new additive migration `0002_tourist_profiles`**. Do not drop your database or remove volumes. Existing `users` and `trips` stay intact.
- Go to http://localhost:8000 and sign in with your previously created email or Google account (or refresh while currently signed in). Open the account menu and complete your profile. Test both accounts; expect one Tourismo row per **distinct Clerk user subject**. Do not merge accounts solely because email addresses happen to match.
- To change verified email, avatar or connected sign-in methods, use **Sign-in & security**, which launches Clerk's managed account panel.

## Verification

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
# Do this after a real Google/email login:
docker compose --env-file .env -f infra/compose.yaml exec db psql -U tourismo -d tourismo -c "SELECT id, auth_subject, display_name, email, profile_completed_at FROM public.users ORDER BY created_at DESC;"
```

Expected: 1 local row for each distinct Clerk subject after a verified sign-in. `profile_completed_at` becomes non-null when a user saves their Tourismo profile.

### Permission checks

- Guest `GET /api/v1/me`, `PATCH /api/v1/me` or `POST /api/v1/auth/session/bootstrap` → `401`.
- Authenticated Google/email user → a single server-provisioned `public.users` record, never a fabricated role.
- `PATCH /api/v1/me` accepts only `display_name`, `locale`, `home_region`, `bio`; attempts to submit `roles`, `status`, `auth_subject` or `email` → `422`.
- Authenticated users can read/update only their own record via the JWT subject; no arbitrary `/users/{id}` editing endpoint was added.
- Existing trip ownership checks stay unchanged. Guest discovery needs no JWT and creates no user.

## Test coverage / honest limitations

The local backend unit/API suite and TypeScript syntax checks can be run without Clerk. Live Google/email auth, real Clerk Backend API email synchronization, Docker PostgreSQL migrations, and browser end-to-end behavior still require your running development environment and are not claimed to have passed in this release environment.
