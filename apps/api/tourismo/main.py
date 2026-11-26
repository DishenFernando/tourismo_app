import time
from collections import deque
from threading import Lock
import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends
from tourismo.core.config import get_settings
from tourismo.core.database import get_db
from tourismo.geography.routes import router as destination_router
from tourismo.trips.routes import router as trips_router
from tourismo.identity.profile import router as identity_router
from tourismo.admin.routes import router as admin_router
from tourismo.vendors.routes import router as vendor_router, admin_router as vendor_admin_router
from tourismo.vendors.documents import router as vendor_documents_router, admin_router as vendor_documents_admin_router
from tourismo.listings.routes import public_router as listings_public_router, vendor_router as listings_vendor_router, admin_router as listings_admin_router
from tourismo.listings.media import vendor_router as listing_media_vendor_router, public_router as listing_media_public_router
from tourismo.demo.routes import router as demo_router
from tourismo.maps.routes import router as map_router
from tourismo.maps.geo_quality import router as geo_quality_router
from tourismo.reviews.routes import (public_router as customer_reviews_public_router,
    vendor_router as customer_reviews_vendor_router, admin_router as customer_reviews_admin_router)
from tourismo.admin.media import admin_router as media_admin_router, public_router as media_public_router
from tourismo.enquiries.routes import (traveler_router as enquiries_traveler_router,
    vendor_router as enquiries_vendor_router, admin_router as enquiries_admin_router)

from tourismo.notifications.routes import router as notifications_router, admin_router as announcements_admin_router
from tourismo.navigation.routes import router as travel_navigation_router

settings = get_settings()
_guest_rate_buckets: dict[str, deque[float]] = {}
_guest_rate_lock = Lock()


def over_guest_limit(request: Request) -> bool:
    """Basic per-process guard for expensive anonymous endpoints.

    Production must also use a shared edge/Redis-level limiter across replicas.
    """
    if request.url.path not in ('/api/v1/navigation/estimate', '/api/v1/trips/preview', '/api/v1/destinations', '/api/v1/listings', '/api/v1/map/points', '/api/v1/map/viewport', '/api/v1/map/nearby', '/api/v1/map/itinerary-places', '/api/v1/map/resolve-location') and not request.url.path.startswith('/api/v1/reviews/'):
        return False
    remote = request.client.host if request.client else 'unknown'
    key = f'{remote}:{request.url.path}'
    current = time.monotonic()
    with _guest_rate_lock:
        if len(_guest_rate_buckets) > 5000:
            for old_key, history in list(_guest_rate_buckets.items()):
                if not history or current - history[-1] > 60:
                    del _guest_rate_buckets[old_key]
        bucket = _guest_rate_buckets.setdefault(key, deque())
        while bucket and current - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= (5 if request.url.path == '/api/v1/navigation/estimate' else (12 if request.url.path == '/api/v1/map/resolve-location' else settings.rate_limit_requests)):
            return True
        bucket.append(current)
    return False

app = FastAPI(title='Tourismo API', version='0.1.0',
              docs_url='/api/docs' if settings.app_environment != 'production' else None,
              redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(',')],
                   allow_credentials=False, allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'],
                   allow_headers=['Authorization', 'Content-Type', 'X-Request-ID'])


@app.middleware('http')
async def request_controls(request: Request, call_next):
    started = time.monotonic()
    request_id = str(uuid.uuid4())
    if over_guest_limit(request):
        response = JSONResponse(status_code=429, content={'error': {
            'code': 'RATE_LIMITED', 'message': 'Too many requests. Try again shortly.', 'request_id': request_id}})
        response.headers['Retry-After'] = '60'
        return response
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(self)'
    response.headers['Server-Timing'] = f'app;dur={(time.monotonic() - started) * 1000:.0f}'
    return response


@app.get('/api/v1/health/live', tags=['health'])
def live():
    return {'status': 'ok'}


@app.get('/api/v1/health/ready', tags=['health'])
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        return JSONResponse(status_code=503, content={'status': 'unavailable'})
    return {'status': 'ok'}


@app.get('/api/v1/auth/config', tags=['auth'])
def auth_config():
    return {'google_enabled': settings.auth_ready, 'email_otp_enabled': settings.auth_ready,
            'phone_otp_enabled': False, 'managed_provider_configured': settings.auth_ready}


app.include_router(identity_router)
app.include_router(media_admin_router)
app.include_router(media_public_router)
app.include_router(destination_router)
app.include_router(trips_router)
app.include_router(admin_router)
app.include_router(vendor_router)
app.include_router(vendor_admin_router)
app.include_router(vendor_documents_router)
app.include_router(vendor_documents_admin_router)
app.include_router(listings_public_router)
app.include_router(listings_vendor_router)
app.include_router(listings_admin_router)
app.include_router(listing_media_vendor_router)
app.include_router(listing_media_public_router)
app.include_router(demo_router)
app.include_router(map_router)
app.include_router(geo_quality_router)
app.include_router(customer_reviews_public_router)
app.include_router(customer_reviews_vendor_router)
app.include_router(customer_reviews_admin_router)
app.include_router(enquiries_traveler_router)
app.include_router(enquiries_vendor_router)
app.include_router(enquiries_admin_router)
app.include_router(travel_navigation_router)
app.include_router(notifications_router)
app.include_router(announcements_admin_router)

# Statically compiled React is served by this API container on Render.
web_dist = Path(settings.web_dist_path)
if web_dist.is_dir() and (web_dist / 'index.html').is_file():
    app.mount('/assets', StaticFiles(directory=web_dist / 'assets'), name='assets')
    app.mount('/brand', StaticFiles(directory=web_dist / 'brand'), name='brand')

    @app.get('/{full_path:path}', include_in_schema=False)
    def spa(full_path: str):
        path = (web_dist / full_path).resolve()
        if path.is_relative_to(web_dist.resolve()) and path.is_file():
            return FileResponse(path)
        return FileResponse(web_dist / 'index.html')
