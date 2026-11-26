# TOURISMO — Sri Lanka's guest-first tourism platform

> **Development package:** Phase 0 planning + Phase 1 working software foundation.  
> **Requirements:** `docs/MASTER_BLUEPRINT_v1.1.md` is authoritative.  
> **Status:** Prototype foundation, NOT an approved commercial or fully integrated tourism platform.

## What works in the source now

- Official Tourismo SVG and PNG assets embedded in an editorial, responsive React + Tailwind interface.
- Homepage with public destination search and public destination records pulled from PostgreSQL/PostGIS.
- Example place-name-only destination seeds: Nuwara Eliya, Anuradhapura, Kandy, Galle, Ella. Every record is explicitly **SAMPLE** and has no fabricated vendor, photo, rating, schedule, weather, capacity or price claims.
- Guest trip editor: destination, dates, adults, **individual child ages**, editable itinerary day/stops, editable category costs, budget cap, local print and session-storage draft.
- Anonymous public `POST /api/v1/trips/preview` calculates truthful arithmetic on the visitor's **own entries** without creating a user profile.
- Managed-auth configuration hooks for Google sign-in and verified email OTP through Clerk; the integration is only active once you add a real Clerk tenant and matching keys. **No fake auth**.
- Server verifies a signed Clerk session's JWKS, issuer, expiration, audience (if set), origin (`azp`) and subject. A verified `sub` provisions exactly one local user under a unique key.
- Private `POST /api/v1/trips`, `GET /api/v1/trips` and `GET /api/v1/trips/{id}` enforce ownership, and require a verified login; private save occurs **only after the user confirms** following authentication.
- PostgreSQL schema and Alembic migration for identities, roles, content sources, example destinations and translations, private cloud trips and future audit events.
- Stateless health/auth config APIs, unit tests, conditional PostgreSQL integration tests, GitHub Actions build/test workflow.
- An organization-wide guest-preview per-process rate guard (a shared edge-level limiter is still required for scaled deployment).

**Not yet implemented:** Actual provider listings, occupancy-combination search, live 2D maps, complete CMS, business verification, weather/transport integrations, reviews, AI, billing, subscriptions and administrator workflows. These remain in their original phased roadmap. There is no tourist booking/checkout.

## 1. Prerequisites on Windows (VS Code)

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) with WSL2 backend and start it.
2. Install [Git](https://git-scm.com/) and [VS Code](https://code.visualstudio.com/).
3. Recommended for separate frontend hot reload: Node.js 22 LTS and Python 3.12.
4. Extract `Tourismo_Phase0_Phase1_Foundation.zip` into your projects directory and open **its folder** with VS Code.

## 2. Easiest start: ONE Docker Compose command

Open **VS Code → Terminal → New Terminal → PowerShell** in the project root:

```powershell
Copy-Item .env.example .env
# Optional: edit .env to add real managed-auth settings before production-style login testing.
docker compose --env-file .env -f infra/compose.yaml up --build -d
```

Go to **http://localhost:8000**. Useful endpoints:

- Home: `http://localhost:8000`
- Discovery: `http://localhost:8000/discover`
- Guest planner: `http://localhost:8000/plan`
- API docs (development): `http://localhost:8000/api/docs`
- Health: `http://localhost:8000/api/v1/health/live`
- Public destinations: `http://localhost:8000/api/v1/destinations`

Validate from PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/live
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
Invoke-RestMethod http://localhost:8000/api/v1/destinations?q=Nuwara
Invoke-RestMethod http://localhost:8000/api/v1/auth/config
```

Confirm guest budget preview, *without any login*:

```powershell
$payload = @{
  destination_slug = 'nuwara-eliya'
  title = 'Six friends trip'
  adults = 6
  children_ages = @()
  budget_limit_minor = 9000000
  budget_items = @(@{
    category = 'transport'
    description = 'Our own estimate'
    minimum_minor = 1000000
    expected_minor = 1500000
    maximum_minor = 2000000
  })
} | ConvertTo-Json -Depth 8
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/trips/preview -ContentType 'application/json' -Body $payload
```

The returned numbers are calculations of your input, **not real travel quotes**.

View container logs:
```powershell
docker compose --env-file .env -f infra/compose.yaml ps
docker compose --env-file .env -f infra/compose.yaml logs -f app
```

Stop without removing DB data:
```powershell
docker compose --env-file .env -f infra/compose.yaml down
```

**Only if you want to erase development data:** `docker compose --env-file .env -f infra/compose.yaml down -v`.

## 3. Live React editing in VS Code (without rebuilding Docker each edit)

1. Start Compose with the above command. Backend is available on port 8000 and database in the Compose private network.
2. In a second VS Code PowerShell terminal:

```powershell
cd apps/web
Copy-Item .env.example .env
npm install
npm run dev
```

3. Visit `http://localhost:5173`. Vite proxies requests beginning `/api` to `http://localhost:8000`.
4. Change `apps/web/src/features/Home.tsx`, `Discover.tsx`, `Planner.tsx`, or `styles.css` and save to see updates in the browser.
5. To run the frontend build and tests:

```powershell
npm run build
npm test
```

To run Python tests on Windows, create a separate virtual environment:

```powershell
cd apps/api
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:PYTHONPATH = '.'
python -m pytest tests -q
```

The external PostgreSQL integration test is skipped unless `TEST_DATABASE_URL` points to a **separately migrated disposable test database**. Never use production for test cleanup.

## 4. Connect real Google login and verified email codes

By default, **all public screens and guest drafts work without Clerk credentials**. Protected operations respond `401` and cannot be bypassed by entering a fake user ID. Configure Clerk only when ready to test real sign-in.

1. Create a Clerk app: https://dashboard.clerk.com/ . Enable Google sign-in and **email verification code** under your chosen auth settings.
2. Configure authorized development origins (for example `http://localhost:8000` and `http://localhost:5173`) according to Clerk's dashboard instructions. Verify which domains your actual Clerk tenant allows.
3. In **root `.env`**, set:
   - `CLERK_ISSUER`: HTTPS issuer URL of your Clerk app (must match token `iss` exactly).
   - `CLERK_JWKS_URL`: your Clerk Frontend API JWKS endpoint ending `/.well-known/jwks.json`.
   - `ALLOWED_AUTH_ORIGINS`: the exact authorized frontend origins to validate token `azp`.
   - `CLERK_AUDIENCE` (optional for default Clerk session tokens; configure if using a JWT template with `aud`).
   - `VITE_CLERK_PUBLISHABLE_KEY`: **public** Clerk key used at frontend build time.
4. If running Vite separately, put `VITE_CLERK_PUBLISHABLE_KEY` in `apps/web/.env` too.
5. Rebuild the app after changing a frontend build-time key: `docker compose --env-file .env -f infra/compose.yaml up --build -d app`.
6. Test guest browse -> Plan -> Save across devices -> real Google/email sign-in -> **Confirm save** -> Saved trips. The draft should remain if login is cancelled.
7. For production, independently review privileged MFA, session revocation, cross-origin policy, and account linking; Clerk free-tier capabilities may not meet finance/admin assurance requirements.

**Do not put `CLERK_SECRET_KEY`, SMS API keys, passwords, or private documents inside Vite variables.** No simulated email/SMS code is ever generated by Tourismo.

## 5. Database migrations and developer commands

The Docker image runs `alembic upgrade head` before starting a single backend process. For review:

```powershell
docker compose --env-file .env -f infra/compose.yaml exec app alembic current
docker compose --env-file .env -f infra/compose.yaml exec app alembic history
```

When the schema changes, add a reviewed new migration instead of modifying `0001_foundation.py` in deployed environments. One-instance automatic migration is convenient for the demo only; production deployment needs a separate gated migration job and a rollback plan.

## 6. Demo hosting pathway

1. Push the repository to GitHub (keep `.env` secret; `.gitignore` excludes it).
2. Configure a **separate** Neon PostgreSQL database and enable PostGIS (test permission first). Use a full SQLAlchemy URL `postgresql+psycopg://...` and Neon-required SSL/TLS query parameters.
3. Deploy the Dockerfile at `infra/Dockerfile` to Render, setting `DATABASE_URL` as an **environment secret**. For real login, provide the Clerk server settings plus the **build-time** publishable key and the actual Render frontend domain in the origin allowlist.
4. Confirm schema migration, `health/ready`, sample public search, security headers and private API denial.
5. Configure custom domain, HTTPS, SEO strategy, backups/restore and monitoring before treating the service as commercial. Render Free may sleep and storage is ephemeral; Neon Free has quotas.

`render.yaml` is an illustrative starting manifest, **not a verified paid-production deployment configuration**. External credentials, permitted services and human acceptance tests remain necessary.

## 7. Folder layout

```
Tourismo/
├── .github/workflows/ci.yml
├── .env.example
├── README.md
├── render.yaml
├── apps/
│   ├── api/
│   │   ├── tourismo/
│   │   │   ├── core/       # configuration, database, models, geography SQL type
│   │   │   ├── identity/   # managed session verification and JIT profile
│   │   │   ├── geography/  # public destination search
│   │   │   ├── trips/      # budget models, preview, protected storage
│   │   │   └── main.py     # FastAPI and compiled web hosting
│   │   ├── migrations/versions/0001_foundation.py
│   │   ├── tests/
│   │   └── requirements*.txt
│   └── web/
│       ├── public/brand/   # original PNG/SVG logo pack
│       ├── src/app/        # auth provider and routing
│       ├── src/components/ # layout
│       ├── src/features/   # home, discovery, destination, planner, saved
│       ├── src/i18n/       # English/Sinhala/Tamil structure
│       └── src/lib/        # API client, local guest draft, tests
├── infra/compose.yaml
├── infra/Dockerfile
└── docs/
    ├── MASTER_BLUEPRINT_v1.1.md
    ├── Tourismo_Architecture_Diagram.png
    ├── PHASE_0_DISCOVERY.md
    └── ARCHITECTURE_AND_ROADMAP.md
```

## 8. Current test evidence and honest limitations

- Backend stateless test suite: **9 tests passed** in the author's available environment.
- Python syntax compilation passed.
- Docker was **not available** in the authoring environment: full Compose startup, real PostgreSQL migration and browser end-to-end checks must be performed locally or CI.
- Frontend dependency installation timed out in the authoring environment; browser build and Vitest execution were not independently confirmed there.
- Auth Google/email cannot be fully integration-tested without your actual Clerk test tenant.
- Repeated Save on the same browser draft is server-side idempotent. Cloud trips are read-only snapshots in Phase 1; full editing/versioning is Phase 6.
- Automated CI configuration and tests are provided but GitHub workflow runs have not been observed.

### Phase 1 completion gate (before advancing to Phase 2)
- [ ] Compose up runs and database schema migrates cleanly.
- [ ] `/api/v1/destinations` returns sample-labeled entries without auth.
- [ ] Local guest planner survives navigation and remains useful with zero credentials.
- [ ] Real Google and email OTP flows create a single verified profile each.
- [ ] Guest draft is saved **only with explicit confirmation**; sign-in cancellation preserves browser state.
- [ ] 401 missing session; 404 on another user's private trip; no role escalation.
- [ ] CI backend/frontend/PostGIS integration jobs pass.
- [ ] Accessibility/response at 320px, tablet, laptop and desktop manually verified.
- [ ] No tourist checkout, fake listing, unsupported live availability, or private file leakage.

## Original references and outstanding decisions

Read `docs/PHASE_0_DISCOVERY.md` and `docs/ARCHITECTURE_AND_ROADMAP.md` for the full blueprint-preserving business decisions, module dependencies, future database domains, phase roadmap and acceptance gates. The original blueprint has not been replaced with a narrower feature specification.

## Phase 1 update — Accounts, profiles and automatic user provisioning

See [`docs/PHASE1_ACCOUNTS_AND_PROFILES.md`](docs/PHASE1_ACCOUNTS_AND_PROFILES.md) for the complete setup, safety notes, DBeaver SQL and acceptance tests.

- Fixed missing PostgreSQL user rows: after a verified Clerk Google/email login, the frontend calls `POST /api/v1/auth/session/bootstrap` to provision the corresponding user by its verified Clerk subject.
- Added a signed-in avatar/name dropdown (desktop and mobile), an optional completion reminder and a private, editable `/account` page.
- Added safe `GET /api/v1/me` and `PATCH /api/v1/me` with server-side authorization and schema validation.
- Added additive migration `0002_tourist_profiles`, preserving existing users/trips.
- `CLERK_SECRET_KEY` is **optional** and **backend-only**, needed for automatic verified-email sync into PostgreSQL; do not include it in a frontend bundle or Git. Existing `CLERK_ISSUER`, `CLERK_JWKS_URL`, `VITE_CLERK_PUBLISHABLE_KEY` still apply.
- These updates do not add tourist bookings, payments, artificial users, or public exposure of private profile fields.

## Phase 2.5 — Pilot visitor guides and sourced attractions

Five existing destination guides (Kandy, Galle, Anuradhapura, Sigiriya, Nuwara Eliya) now receive deeper source-referenced **English editorial samples**, 11 additional POIs and practical visiting tips. The public destination page includes attraction-category filters and individual POI tips. Migration `0007_pilot_destination_guides` upgrades only unmodified sample guides with no editor revisions; it never overwrites published/reviewed content. New attractions added to published destinations remain drafts.

Read `docs/PHASE2_PART5_PILOT_GUIDES.md` for sources, limitations, DBeaver checks and the optional `scripts/verify-phase25.ps1` read-only smoke test. This does not finalize image licensing, translations, or Phase 2 acceptance.

## Phase 3.1 — Vendor onboarding

See [vendor application and manual verification guide](docs/PHASE3_PART1_VENDOR_ONBOARDING.md). Four additive private vendor tables and the `/vendors` and `/admin/vendors` screens have been added. The implementation does not yet upload private documents, publish listings, or activate trials.


## Phase 7 — Customer reviews and trust (changes-only release)

Traveler ratings, independently moderated comments, provider responses, and abuse reports are documented in [`docs/PHASE7_CUSTOMER_REVIEWS_AND_TRUST.md`](docs/PHASE7_CUSTOMER_REVIEWS_AND_TRUST.md). New migration `0016_customer_reviews`; run `scripts/verify-phase7.ps1` after local deployment. The unrelated `service_listing_reviews` editorial approval table is unchanged.


## Phase 8 — Private tourist/vendor enquiries (source update)

See [Phase 8 quick start](docs/PHASE8_START_HERE.md) and [Phase 8 technical/operating documentation](docs/PHASE8_TOURIST_VENDOR_ENQUIRIES.md). It adds new `/enquiries`, `/vendor/enquiries`, and `/admin/enquiry-reports` pages, plus migration `0018_service_enquiries`. Guests can still browse; this remains a no-booking/no-payment application. Phase 7.1 live deployment is a prerequisite.
