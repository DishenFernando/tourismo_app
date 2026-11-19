# Tourismo — Phase 2.1: Sourced destinations & POIs

## Scope delivered

- PostgreSQL/Alembic migration `0003_destination_intelligence` adds `destination_guides`, `poi`, and `poi_translations`; an index on POI geography enables later radius search.
- Five **sample** English guides and five reference POIs, with links to official municipal/provincial or UNESCO source pages. The samples are **not** marked `published` or `verified_at`; no invented costs, opening hours, vendors, rating, availability, or photo licenses.
- Anonymous, typed public read APIs with English fallback when Sinhala or Tamil is requested but hasn't been reviewed:
  - `GET /api/v1/destinations/{slug}/guide?locale=en|si|ta`
  - `GET /api/v1/destinations/{slug}/pois?locale=en|si|ta&category=heritage`
- Redesigned destination detail screen includes source links, sample status, highlights, POI cards, language selection and planning handoff.
- Draft content is excluded server-side, even when clients request it. Original destinations, profiles, authentication, trips and cloud-saving routes remain intact.

## Official sources used (links, not copied imagery)

- [Anuradhapura, UNESCO World Heritage Centre](https://whc.unesco.org/en/list/200/)
- [Galle Fort, UNESCO World Heritage Centre](https://whc.unesco.org/en/list/451/)
- [Sacred City of Kandy, UNESCO World Heritage Centre](https://whc.unesco.org/en/list/450/)
- [Nuwara Eliya landmarks, Municipal Council](https://nuwaraeliya.mc.gov.lk/index.php/information/about)
- [Ella attractions, Uva tourism portal](https://visituva.lk/zone/ella)

The example editorial text is newly written and not a reproduction of the linked sources. These source links are supplied for verification, not as licenses for photography. Date-sensitive and commercially sensitive facts are deliberately excluded until editorial checking.

## Apply on existing clone (PowerShell)

1. Back up or commit your pending local source edits.
2. Download `Tourismo_Phase2_Part1_Changes_Only.patch` and put it in `Downloads`.
3. From the Tourismo project root:

```powershell
$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase2_Part1_Changes_Only.patch"
git apply --check $patch
git apply $patch
docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
```

If the check fails, stop and review local differences rather than forcing the patch. If the user does not use Git, the alternative update-only ZIP has only changed files, but overwrites those exact files.

4. Open `/destinations/nuwara-eliya`, `/destinations/ella`, `/destinations/kandy`, `/destinations/galle` and `/destinations/anuradhapura`.
5. Verify the database and APIs:

```sql
SELECT version_num FROM alembic_version;
SELECT d.slug, g.locale, g.content_status, g.verified_at
FROM destination_guides g JOIN destinations d ON d.id = g.destination_id ORDER BY d.slug;
SELECT p.slug, p.category, p.content_status, s.url AS source_url
FROM poi p LEFT JOIN content_sources s ON p.source_id = s.id ORDER BY p.slug;
```

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/destinations/galle/guide
Invoke-RestMethod http://localhost:8000/api/v1/destinations/ella/pois
```

Existing `.env`, Docker Compose, Clerk credentials, database volumes and existing user/trip rows must remain untouched. Never run `docker compose down -v`.

## Verification

Python unit and API tests are runnable with `PYTHONPATH=apps/api python -m pytest -q apps/api/tests` from the root. Tests requiring a disposable PostgreSQL/PostGIS instance use `TEST_DATABASE_URL` and are skipped in environments without it. The full React production build and live Docker/Clerk flows must be run locally.

## Not yet implemented (later Phase 2 increments)

- Secure editor-only CMS, revision/audit history, editorial approval and publish controls
- Human-reviewed Sinhala/Tamil translations, quality gates, full geographic hierarchy, vetted media
- Licensed destination photographs, seasonal advice, accessibility/transport details and verified fees
- MapLibre 2D interactive pins and routing (scheduled Phase 5)

Current data remains labeled sample; obtaining a source URL is not the same as editor approval.
