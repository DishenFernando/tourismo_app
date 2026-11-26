-- TOURISMO Phase 5.4: optional, READ-ONLY PostGIS query timing.
-- Run only on the local/test database. EXPLAIN ANALYZE executes SELECT statements.
-- No CREATE/UPDATE/DELETE, no new index is assumed without measured results.
-- Note: these are simplified diagnostic counterparts of the API queries; they
-- do NOT replace the server's public listing visibility/expiration policy.
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id FROM destinations
WHERE content_status IN ('sample','published') AND location IS NOT NULL
  AND ST_Y(location::geometry) BETWEEN 5.5 AND 10.1
  AND ST_X(location::geometry) BETWEEN 79.4 AND 82.1
LIMIT 181;

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id FROM poi
WHERE content_status IN ('sample','published')
  AND latitude BETWEEN 5.5 AND 10.1 AND longitude BETWEEN 79.4 AND 82.1
LIMIT 181;

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id FROM service_listings
WHERE status = 'published'
  AND latitude BETWEEN 5.5 AND 10.1 AND longitude BETWEEN 79.4 AND 82.1
LIMIT 181;
