# Tourismo Phase 10B — Travel Directions, Optional Email Delivery and Guest-Friendly Discovery

**Status:** Changes-only source upgrade, not a claim of live email delivery or complete Sri Lankan transit coverage. Expected current database revision: `0019_notifications_trust`. New revision: `0020_travel_email`. No user data is deleted by the upgrade.

## Why these changes matter

The traveler journey should answer **Where is it? How far? How do I get there?** without requiring them to type geographic coordinates or understand technical terms. The vendor journey should deliver important notifications outside the app, without making the review/enquiry endpoint wait on email. Both need transparent failure modes.

### Implemented source behavior

| Experience | Result |
|---|---|
| Public destination or published real service | **How to get there** panel appears if a sourced point exists; when a point is missing, displays an honest unavailability message |
| GPS location | Optional, only by clicking "Use my location"; no coordinates persisted to Tourismo database |
| Straight-line distance | Calculated in the browser on opt-in; explicitly **not** a road-route distance |
| Travel modes | Driving, bus/train (transit), walking, cycling; the main directions link opens Google Maps with the selected mode and destination coordinates |
| Google route estimate | Optional server-side Routes API with a paid/restricted API key; returns road km and estimated minutes if the API returns a route; otherwise no invented numbers |
| Sourced pin integrity | Service must pass the existing `_public_query()` eligibility; destination must be public or editorial sample with an actual PostGIS point; no imaginary pins |
| Service search | One-click **Show services near me** automatically applies a 20-km default and distance sort; manual latitude/longitude hidden in Advanced details |
| Notification email | PostgreSQL trigger adds outbox records in the same transaction as existing `user_notifications` inserts, covering review/enquiry/vendor approval/welcome activity notifications |
| Email preferences | Signed-in user can enable/disable activity mail and opt into release-update email; release email is **off by default** |
| Broadcasts | An admin-created `platform_announcements` row creates a background fan-out job; a separate worker pages through opted-in user IDs |
| Sending | Optional Resend provider with HTTPS API, verified domain, stable idempotency key, 5-attempt retry and exponential delay; provider accepted ≠ inbox delivered |
| Delivery worker | Separate opt-in Compose overlay; **not** run inside web request handlers or all Uvicorn replicas |

### Not claimed or invented

No current live bus positions, nationwide official bus/rail route database, railway ticketing, route-fare guarantees, toll guarantees, accessibility-compliant pedestrian routing, exact entrance pin for a mountain, or automatic road-distance calculations without a licensed route provider. Google Maps transit availability depends on the locality and provider coverage. We do not render proprietary Google Routes polylines over OSM/Leaflet maps without reviewing license terms.

### Required external setup

- Google Maps URLs work without an API key. The optional in-app **route km / ETA** requires Google Maps Platform Routes API billing, quota limits and a server-side `GOOGLE_ROUTES_API_KEY`. Do not expose it as `VITE_*` or commit to Git.
- Email requires a verified sending domain, `RESEND_API_KEY`, `NOTIFICATION_EMAIL_FROM`, `PUBLIC_APP_ORIGIN`, `EMAIL_ENABLED=true`, and an independently running `email-worker` container. No provider is silently enabled. Configure SPF/DKIM/DMARC and bounce/complaint management before public launch.
- `.env` and `infra/compose.yaml` remain untouched by this patch. Run the optional overlay only after deployment.

## Storage and security

`0020_travel_email` adds `email_preferences`, `email_outbox`, `email_broadcast_jobs`, and two AFTER INSERT database triggers. No existing review, provider, enquiry, profile or announcement row is changed. New tables contain IDs and delivery metadata, **not** copies of private review messages or email addresses. Worker looks up the **current verified account email** at send time. Email bodies are derived from already-generated notification title/body and internal links; HTML is escaped.

Guest origin coordinates are sent to Tourismo only after the user clicks **Check route distance & time** and may be sent by Tourismo to Google when the API is configured. Opening Google Maps separately shares location with Google under its own privacy notice. `Cache-Control: no-store` protects route estimate responses against intermediate caching; origin coordinates are not stored. Production access logs/proxies must avoid logging full request payloads. Add per-user/edge rate limiting and budget alerts before commercial deployment.

## Release emails, consent and operational reliability

Release emails are opt-in only. Existing users without preferences do not receive release emails. Admin release publishing remains explicit **after verifying deployment**, not tied to container restarts. The email worker queues opted-in recipients in batches and retries provider errors without blocking business APIs. Email delivery is best-effort until provider webhook delivery/complaint handling is built. Do not call an API acceptance “delivered to inbox.”

User preferences can disable email, but the in-app inbox and review moderation are unaffected. Email delivery is not part of payment or sign-in credential verification; Clerk remains the identity provider. The email-worker container is an independently operated optional component. A production deployment needs monitoring for queued/failed outbox rows, a cleanup/retention policy and provider webhooks for bounces and complaints. These are mandatory before full public launch.

## Acceptance tests (must be performed on real PostgreSQL/Clerk)

1. Verify `0019_notifications_trust` is the current DB head; take database plus private-document backup.
2. Apply patch and build; confirm `0020_travel_email` installed and three tables plus two triggers exist.
3. Guest opens a public hotel/restaurant and a destination with coordinates. Before granting GPS permission, no distance should be fabricated. Click GPS and see straight-line km. Open driving and transit directions in Google Maps; if transit is unsupported, show the provider's actual result.
4. With no Google API key, click route estimate: it should say unavailable, not return a guessed distance/time. Configure a restricted API key in a staging environment; check route distance and ETA originate from provider data, and absent routes return no estimates.
5. Check a listing without coordinates, rejected vendor, and fictional `/demo/listings`: never create invented travel points.
6. Sign in as Business Owner A, Traveler B and unrelated C. B submits a safe review or enquiry; Owner A receives an in-app notification. C must not receive it.
7. With sender verified and configured, test email-worker against test inbox. Verify exactly one provider-accepted mail for the notification even when request is repeated with the same notification dedupe key.
8. Disable activity mail, trigger another event: inbox receives it, email is suppressed. Enable release mail and publish a unique admin announcement after staging verification: only opted-in users receive a mail.
9. Simulate provider 429/500: review/enquiry still succeeds; email job retries. Check recipient and retry state without logging secrets. Check account sign-out and email preference changes.
10. Check keyboard navigation and mobile screens (320/375/768/1024/1440px), map and saved trips, review images, notification bell, navbar (no sideways scroll), and vendor dashboard.
11. Verify secure public HTTPS domain, Google/provider billing quota, mail DNS authentication and real-world route accuracy sample across districts before public launch.

### Future UX and data priorities

Use verified entrances/stops (not just centroids) when vendors provide evidence, address/landmark autocomplete backed by a licensed geocoder, understandable transfer details for bus/train (line, operator, last-mile), wheelchair accessibility filters with verified evidence, Sinhala/Tamil human-reviewed journey copy, trip-budget integration for travel cost estimates with provenance, optional push notifications with consent, guest trip draft persistence, support/FAQ, error recovery and accessibility audits. None should be advertised as fully built in this increment.

### Official provider references

- Google Maps URLs: https://developers.google.com/maps/documentation/urls/get-started
- Google Routes API: https://developers.google.com/maps/documentation/routes
- Transit caveats: https://developers.google.com/maps/documentation/routes/transit-route
- OSM hosted tile policy: https://operations.osmfoundation.org/policies/tiles/
- Resend: https://resend.com/docs/send-with-python and https://resend.com/pricing
