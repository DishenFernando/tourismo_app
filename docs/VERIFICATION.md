# Foundation verification evidence — 19 November 2026

## Checks executed locally in authoring environment

| Check | Result | How |
|---|---|---|
| Python foundation tests | **PASS: 9** | `PYTHONPATH=. pytest -q tests` from `apps/api` |
| PostgreSQL integration tests | **SKIPPED: 2** | Conditional `TEST_DATABASE_URL` unset; Postgres/Docker not available here |
| Backend Python syntax | **PASS** | `python -m compileall -q tourismo migrations tests` |
| Alembic offline SQL generation | **PASS** | `PYTHONPATH=. alembic upgrade head --sql` |
| TypeScript syntax transpilation | **PASS** | Parsed/transpiled all `.ts`/`.tsx` sources with globally installed TypeScript 5.8.3 |
| Full TypeScript type-check / Vite build | **NOT VERIFIED** | `npm install` timed out in authoring environment (no installed project dependencies) |
| Real DB migration / PostGIS query | **NOT VERIFIED** | No local PostgreSQL/Docker binary accessible |
| Real Clerk Google/email OTP | **NOT VERIFIED** | Requires identity-provider tenant and keys |
| Browser/mobile interaction | **NOT VERIFIED** | Needs running server, installed frontend dependencies and browser |
| Container/image scan and load test | **NOT EXECUTED** | Must run in CI/staging before commercial launch |

These are **not** claims that the full release has passed security or deployment acceptance. The root README gives exact VS Code and Docker commands to perform those tests. GitHub Actions defines full builds and a migrated PostgreSQL integration test, but no GitHub result has been observed.

## Phase 1 critical tests still required
1. Docker `up --build` and both health checks; destination sample read from migrated PostGIS.
2. Clerk's Google and email-code flows tested with real configured tenant.
3. Guest changes are kept after auth cancellation/redirect.
4. Two real sessions cannot access each other's trips; test 401/404 and tampered JWT.
5. Guest trip save double submission produces only one cloud copy using client draft ID.
6. Browser keyboard/mobile design and validated accessibility.
7. Source rights/security review, production secrets handling, deploy rollback and backup recovery.
