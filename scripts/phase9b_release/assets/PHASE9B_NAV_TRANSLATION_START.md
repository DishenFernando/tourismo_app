# Tourismo Phase 9B-1 — Navigation refinement and editorial translation readiness

**Scope:** UX fix from screenshot, independent-language-review preparation, diagnostics for editorial load failures. **Not** a claim that all destination pages are translated.

## Navbar: screenshot findings and changes

- Desktop links in the supplied screenshot wrap into two lines (`Plan trip`, `Saved trips`, `For businesses`). Keep them on one line and permit in-place keyboard-accessible horizontal scrolling only if a constrained desktop width truly cannot fit. Mobile navigation remains owned by the original Header component.
- The tiny `EN · SI/TA planned` status in the main header competes with navigation, while the large notice bar redundantly explains the language preview. The update attempts safe removal of the obsolete status label where its markup is recognized. If the old element is unfamiliar, the generator leaves it untouched and reports that fact.
- Replace the long constantly displayed language notice with compact language/accessibility controls and an optional "Language coverage" details disclosure. Keep the important limitation discoverable, including for screen readers.
- Preserve the avatar/account menu, sign-in flow, route permissions, vendor actions, start-planning CTA, accessibility skip link and all primary links. No product/business data or database revision is changed.
- Include visible keyboard focus and reduced-motion preferences. Validate 320, 375, 768, 1024, 1280, 1440 and 1775 px widths; horizontal navigation must not trigger whole-page overflow.

## Phase 9B-1: usable editorial translation workbench

- New page `/admin/translation-workbench` allows **admin/editor authenticated profiles** to inspect handoff `.jsonl` or `.ndjson` content **locally in their browser**. The tool does not upload, save or publish translated material.
- Records use the same format as `scripts/audit-phase9-content.py` from Phase 9A: content type, slug, HTTPS source, English title+summary, and optional Sinhala/Tamil translations with `missing`, `draft`, `reviewed` states. A reviewed translation requires a distinct named translator and reviewer and a valid review date.
- A passing format audit does **not** verify translation accuracy, image copyright, cultural details, opening times, safety advice or editorial authority. These still need human/native-speaker review and manual CMS publication approval.
- Supports up to 2 MB / 2,000 lines per local inspection. React escapes all displayed content. Role controls are UI-only; future server publication operations must enforce backend permissions independently.
- Further Phase 9B work: connect translation revisions to actual backend CMS with an additive schema only after inspecting real current models, APIs, content source/approval rules and sample records; add authenticated submission and separate publisher approval; load only approved translations in public API; server-render or prerender metadata and hreflang when approved translations exist. Do not invent translations or silently auto-publish.

## Editorial banner shown in screenshot

`Some editorial content could not be loaded.` indicates a failed content request or processing path. Its exact cause cannot be determined from the screenshot. **Do not remove the warning** or assume unavailable Sinhala content alone caused it.

From the repository root:

```powershell
py -3 .\scripts\phase9b_release\diagnose_editorial_loading.py --root .
```

Open `http://localhost:8000/destinations/<actual-slug>` in the browser, press F12, go to Network > Fetch/XHR, reload the page, and inspect any red/failed request (URL, status and response). In Docker, inspect `docker compose --env-file .env -f infra/compose.yaml logs --tail=150 app`. Compare selecting English versus Sinhala. 401/403, 404, 500 or unavailable translation need different fixes.

## No migration

The installed database head remains `0018_service_enquiries`. This patch changes presentation, adds a client-only translation auditing page, scripts, and docs. It does not change published destination content, review moderation or enquiry state.

## Gate before installation

- Existing Phase 9A must be applied and the full Docker/Vite build accepted.
- Preserve customized Header/App and existing source; generate a **changes-only** patch against the current checkout. Verify `git apply --check` before applying. No file overwrite, force apply, `git reset`, or `docker compose down -v`.
- Test with two user roles (guest and editor), all navigation links, and language preview persistence after rebuild.
