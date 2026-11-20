# Tourismo Phase 4.3 — Advanced Listing Discovery

**Basis:** Tourismo Phase 4.2 + fictional demo catalog, migration `0011_advanced_listings`.
**New revision:** `0012_listing_discovery_indexes`. Changes only discovery APIs, frontend filters, database indexes, and guest route rate limiting. Existing Clerk, vendor documents, admin approval, published-listing revision code, `.env`, and Compose are unchanged.

## What is included

1. **Destination-aware service lookup:** choose among existing public destinations. A match means the same **district**, or an explicitly declared provider **service area**. It is **not** a distance claim, route, or precise POI match. Clicking “Find services in this region” on a destination guide opens the filtered listing directory.
2. **Family suitability before pagination:** accommodation + adults and optional children's ages. PostgreSQL JSONB room policies are compared in an `EXISTS` condition *before* limit/offset. A result means some recorded room type may fit; it does not confirm bookability, available inventory, total family charges, or age-policy completeness.
3. **Radius search:** manually supply latitude/longitude or press **Use my location** in the browser (permission requested only on click); set a radius in (0, 100] km and optionally sort by nearest. PostGIS `geography` computes approximate geodesic, straight-line distances; **not** driving distance, transport duration, or known public access. Only published listings with provider-supplied sourced coordinates can appear.
4. **Combined filters and paging:** category, keyword, province, district, destination, age rules, radius and distance sorting. Limited to 24 results per page, with next/previous buttons. Server still caps limits/offsets.
5. **Performance and safety:** partial region index and partial PostGIS GiST expression index; source backend verification gate on each public query; rate limiting for listing searches. Anonymous requests cannot see draft organizations, private evidence, reviews, unapproved listings, or demo listings.

### Not included

- Interactive tile-backed map, routing/estimated travel time, live provider inventory or prices.
- Real-world validity claims about example demo companies. `demo/listings` stays separate and uses its original limited filters.
- Automatic choice of a center point when a destination is selected. District-level matching deliberately avoids inventing destination coordinates.

## Upgrade safely

```powershell
cd "D:\Tourismo\Tourismo"  # Or the actual folder containing your .env and infra directory.

docker compose --env-file .env -f infra/compose.yaml exec app alembic current
# EXPECTED BEFORE APPLYING: 0011_advanced_listings

$patch = "$env:USERPROFILE\Downloads\Tourismo_Phase4_Part3_Advanced_Discovery_Changes_Only.patch"
git apply --check $patch
git apply $patch
# After application, DO NOT run git apply --check again: it would try to apply twice.

docker compose --env-file .env -f infra/compose.yaml up --build -d
docker compose --env-file .env -f infra/compose.yaml ps
docker compose --env-file .env -f infra/compose.yaml exec app alembic current
# EXPECTED AFTER: 0012_listing_discovery_indexes
```

Keep all Docker volumes. No fake providers are approved/published by this patch.

## URLs and examples

- UI: `http://localhost:8000/listings`
- Destination→services: `http://localhost:8000/listings?destination=kandy`
- Public API regional search: `/api/v1/listings?destination=ella&category=guide`
- Public API family matching: `/api/v1/listings?category=accommodation&adults=2&child_ages=5&child_ages=12`
- Public API radius: `/api/v1/listings?near_lat=6.9271&near_lon=79.8612&radius_km=20&sort=distance`
- Combined: `/api/v1/listings?category=accommodation&adults=2&child_ages=5&destination=kandy&near_lat=7.29&near_lon=80.64&radius_km=40`
- Existing demo: `http://localhost:8000/demo/listings` (if enabled in development). In Phase 4.3 it also supports the regional and family filters; the fictional demo entries remain private drafts. Radius is restricted to the real verified directory because the demo data has no sourced coordinates.

All actual public search results require business verification **and** independent listing publication. The demo companies you seeded are draft/unverified and are intentionally absent from normal `/listings`; it is therefore normal to see zero results in the public search until real providers are approved.

### DBeaver verification

```sql
SELECT version_num FROM public.alembic_version;
SELECT indexname FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'service_listings'
  AND indexname IN ('ix_service_listing_public_regions', 'ix_service_listing_public_geo');
SELECT status, COUNT(*) FROM public.service_listings GROUP BY status;
```

### Validation

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\verify-phase43.ps1
```

A Python suite includes regional matching, bound search queries, age filters, public verification invariants, and migration contract tests. The complete Vite production build and PostGIS integration tests must be run in your real Docker environment. Any failing validation or unknown destination returns a client error rather than silently changing search semantics.
