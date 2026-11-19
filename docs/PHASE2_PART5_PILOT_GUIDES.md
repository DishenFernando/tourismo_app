# Tourismo Phase 2.5 — Five deeper destination pilots

## Scope

Adds source-referenced English visitor guides, practical planning notes and **11 new attraction entries** to the existing 117-place discovery catalog. It also adds category filters, per-attraction visitor tips and links between the pilot guides on the destination page. The other 112 directory entries are not represented as complete guides.

**Pilot places:** Kandy, Galle, Anuradhapura, Sigiriya and Nuwara Eliya.

### Editorial integrity

- New attraction records are `sample` only for sample destinations; for an already-published destination, new attractions are `draft` and remain hidden from guests until editorial approval. All content still needs human review before publication.
- No synthetic hotel/restaurant data, ticket prices, opening hours, provider ratings, booking availability or estimated entrance coordinates are inserted.
- UNESCO coordinates previously inserted by Phase 2.3 remain *property reference points*, not entrances. No new point-of-interest coordinates are guessed.
- Sources are reference links, not a claim of licensing or of an officially endorsed partnership. `verified_at` is not populated by this migration.
- `destination_photos` is unchanged: 18 remotely linked images from Phase 2.2 still require an independent Commons file-page/license audit; we did not add unverified image records.
- Sinhala/Tamil article text is **not fabricated**. English fallback continues until human-reviewed translations are supplied.

### Seed safety

New migration: `0007_pilot_destination_guides`, after `0006_editorial_quality`.

For existing English sample guides, enrich the content **only if** the original overview text still exactly matches the old seed, the status remains `sample`, and the guide has **no revision records**. Published, submitted, rewritten or editorially revised guides remain untouched.

POIs are inserts-only using deterministic UUIDs and a conflict-safe `(destination_id, slug)` constraint. Adding attractions to an already-published destination creates private `draft` records, not public `sample` entries. Existing POI text is never overwritten. Sources are inserted with `ON CONFLICT DO NOTHING`.

The `downgrade()` deliberately doesn't remove editorial records that may have been reviewed or used since the update. The migration does not change any database tables or credentials.

## Source bibliography

| Destination / information | Authoritative link |
|---|---|
| Kandy sacred city and Temple of the Tooth | https://whc.unesco.org/en/list/450/ |
| Royal Botanic Gardens, Peradeniya | https://en.botanicgardens.gov.lk/service/royal-botanic-gardens-peradeniya/ |
| Galle old town, streets and ramparts | https://whc.unesco.org/en/list/451/ |
| Anuradhapura sacred city and Bodhi tradition | https://whc.unesco.org/en/list/200/ |
| Ruwanwelisaya local site mention | https://archaeology.gov.lk/index.php/anucircuit |
| Sigiriya ancient city | https://whc.unesco.org/en/list/202/ |
| Sigiriya water gardens, frescoes and Lion Gate | https://ccf.gov.lk/heritage-sites/sigiriya-rock-fortress/ |
| Nuwara Eliya Gregory Lake and Victoria Park | https://www.nuwaraeliya.mc.gov.lk/index.php/information/about |
| Hakgala Botanic Gardens | https://botanicgardens.gov.lk/service/botanic-gardens-hakgala/ |

Source text is summarized freshly rather than reproduced verbatim. Content still needs local editorial fact-checking before promotion to `published`.

## Apply without replacing the project

1. Apply the Phase 2.5 `.patch` in `D:\Tourismo\Tourismo` **after** Phase 2.4.
2. Verify the patch before modifying files: `git apply --check $patch`; then `git apply $patch`.
3. Run `docker compose --env-file .env -f infra/compose.yaml up --build -d`.
4. Check `docker compose --env-file .env -f infra/compose.yaml ps` and logs.
5. Open five pages under `/destinations/{slug}` and review guide, attractions, source attribution, language fallback and trip planner route.
6. Run `powershell -ExecutionPolicy Bypass -File .\scripts\verify-phase25.ps1` for read-only verification.
7. Review and approve each guide and attraction in `/admin` using the existing server-side editor/admin workflow. **Do not auto-promote sample records in SQL.**

### Read-only checks in DBeaver

```sql
SELECT version_num FROM alembic_version;

SELECT d.slug, g.content_status, length(g.overview) AS overview_characters,
       jsonb_array_length(g.highlights) AS highlights,
       jsonb_array_length(g.local_tips) AS visitor_tips
FROM destination_guides g
JOIN destinations d ON d.id = g.destination_id
WHERE d.slug IN ('kandy','galle','anuradhapura','sigiriya','nuwara-eliya')
  AND g.locale = 'en'
ORDER BY d.slug;

SELECT d.slug, COUNT(*) AS public_attractions
FROM poi p JOIN destinations d ON d.id=p.destination_id
WHERE d.slug IN ('kandy','galle','anuradhapura','sigiriya','nuwara-eliya')
  AND p.content_status IN ('sample', 'published')
GROUP BY d.slug ORDER BY d.slug;
```

## Remaining Phase 2 exit blockers

The five pilots still need independent human approval, accessibility checks, authoritative image licensing verification, fuller location/POI coverage, reviewed Sinhala and Tamil guides, real-device browser tests and live PostGIS integration. Phase 3 vendor onboarding should follow the Phase 2 acceptance review; the blueprint requirements are **not** declared complete by this seed expansion alone.
