# TOURISMO — Phase 9A: Content Quality, Interface Languages & Accessibility

**Release date:** 23 November 2026
**Prerequisite:** Phase 8 source and live migration `0018_service_enquiries` already installed and accepted.
**Database migration:** None. Phase 9A keeps revision `0018_service_enquiries`.
**Release type:** Changes-only Git patch generated against your local Phase 8 source.

## Delivered in 9A

1. EN / SI / TA navigation-label preview with a keyboard-accessible selector and safe browser-local persistence.
2. English page remains the document language because the majority of content is not translated. The selector is explicitly **not** a claim of a fully multilingual application.
3. Keyboard skip-to-content link, focus target, accessible language selection and route-change announcements.
4. Public accessibility-status page at `/accessibility` that states what is supported and what is not verified.
5. Conservative per-route title/description and client-side canonical metadata; account, vendor, admin, demo, saved-trip and enquiry routes are marked noindex client-side.
6. Offline native-editor translation handoff JSONL validator; no direct database updates, no automatic translation or fabricated editorial content.

## Limitations and next slice (9B)

- Native-reviewed destination, attraction and guide translations, including source attribution and revision history, still need a dedicated CMS schema/editorial release.
- Translating a navigation label is **not** translating a destination guide, a vendor's service claims, a regulatory notice or tourism safety instructions.
- English remains the main content language. Do not set `html lang=si` or `ta` for English body copy. Screen-reader pronunciation of translated navigation labels still needs native-speaker testing.
- Client-side SEO metadata is a foundation, not SSR/SSG. For production, add server/prerendered page-specific titles/canonicals/HTTP 404 responses, canonical-domain configuration, a sitemap and robots policy, plus indexing tests.
- The app has not undergone a full WCAG 2.2 AA audit. Native keyboard, mobile screen reader, focus trapping, map list alternative, contrast and touch-target checks remain acceptance gates.
- The content handoff checker validates editorial structure, source HTTPS and separate reviewer attribution; it cannot authenticate the underlying source or guarantee translation quality.

## Native-editor JSONL handoff format

Each line is a single JSON object. Example **illustrative only; not a real destination record or publishable translation**:

```json
{"type":"destination","slug":"example-place","source_url":"https://example.org/source","en":{"title":"Example title","summary":"Example English source summary"},"si":{"status":"missing"},"ta":{"status":"missing"}}
```

When content is translated, `si` and `ta` may have `status: "draft"`, a localized `title`, `summary` and `translated_by`. Before `status: "reviewed"`, provide a **different** human `reviewed_by` and an ISO `reviewed_at` date. Content cannot be marked ready simply by running an AI translator. CMS publication integration is not part of 9A.

Run the offline QA checker:

```powershell
py -3 .\scripts\audit-phase9-content.py .\my-editorial-export.jsonl
```

## Acceptance checklist

- The Phase 8 Docker build, `verify-phase8.ps1` and private tourist/vendor enquiry round-trip pass before 9A.
- `git apply --check` and apply the exact local patch; `npm run build` succeeds in the Docker frontend stage.
- Tab on the landing page shows Skip to main content; activating it focuses the route container.
- Language selector keyboard works; switching English/Sinhala/Tamil changes navigation labels, persists after refresh, and does **not** pretend guides are translated.
- Navigate public and private pages; document title and robots/canonical tags update; private content remains server-protected and is not made public by SEO tags.
- Test 320 px, 375 px, tablet and desktop widths with browser zoom at 200%; review map and modal focus behavior.
- Test screen readers NVDA and VoiceOver; assess untranslated English copy and regional language pronunciation.
- No regressions to Phase 7.1 review safety/photos or Phase 8 enquiry tenant isolation.
- Native editorial reviewer checks and legal/privacy review before exposing regional-language guides in production.

## Reference guidance

- W3C WCAG 2.2: https://www.w3.org/TR/wcag/
- Google Search Central JavaScript SEO: https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics

## Rollback

Revert only the Phase 9A source commit, after checking for any intervening custom code. No database schema changed. Do **not** drop Docker/Postgres volumes, downgrade Phase 8 or remove review media. The safe rollback path is Git source restoration and rebuilding the app image.
